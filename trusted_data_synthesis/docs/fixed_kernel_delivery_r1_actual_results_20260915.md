# R1 固定检查点、公共说明与交付诊断结果

结果身份：`delivery_r1_final_report:5331e401ba1ff37c08f5d6d958f8188dcf9bc956aa5599e57dfe0add5ed397bd`。计划身份：`delivery_r1_plan:b6e225d8bb0bb1f3e2783332d1822c3d3fec7e4227fcd422904a7c93f8ef87e4`。

本轮完成 60 个完整会话及 60 次公开历史单步续接。完整会话只有 **3 个独特开发任务**，
在 9 个微调检查点和 1 个未微调基座、2 个同 R1 工具说明条件下重复执行。
基座不属于 alpha0，单步续接不计自主任务成功或完整财务资格。

## 同 R1 工具下的主要配对结果

Q 为既定完整轨迹财务资格；Δ_doc = Q(R1, Γ_doc) − Q(R1, Γ_0)。每格分母均为 3 题。

| 模型 | 类型 | 原说明 Q | 澄清说明 Q | 配对平均 Δ_doc |
|---|---|---:|---:|---:|
| unfinetuned_base | unfinetuned_base | 0/3 | 0/3 | +0.0000 |
| A_alpha0_11 | finetuned | 0/3 | 0/3 | +0.0000 |
| A_plus_11 | finetuned | 0/3 | 0/3 | +0.0000 |
| A_minus_11 | finetuned | 0/3 | 0/3 | +0.0000 |
| A_alpha0_29 | finetuned | 0/3 | 0/3 | +0.0000 |
| A_plus_29 | finetuned | 0/3 | 0/3 | +0.0000 |
| A_minus_29 | finetuned | 0/3 | 0/3 | +0.0000 |
| A_alpha0_47 | finetuned | 0/3 | 0/3 | +0.0000 |
| A_plus_47 | finetuned | 0/3 | 0/3 | +0.0000 |
| A_minus_47 | finetuned | 0/3 | 0/3 | +0.0000 |

## 执行阶段观测

下列均为‘会话至少出现一次’的计数，阶段可重叠，不能相加为根因或临时总分；计算成功本身不证明所求数量正确。

| 模型群 / 条件 | 会话 | 非空发现 | 非空查询 | 数值读取 | 成功计算 | Final | 完整 Q | 工具错误 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| finetuned / original | 27 | 3 | 0 | 0 | 0 | 0 | 0 | 14 |
| finetuned / gamma_doc | 27 | 0 | 0 | 0 | 0 | 0 | 0 | 19 |
| unfinetuned_base / original | 3 | 0 | 0 | 0 | 0 | 1 | 0 | 2 |
| unfinetuned_base / gamma_doc | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 3 |

## 已见公开历史的单步条件能力

计算前与 Final 前的续接分别汇总，语义检查允许合法替代表达式；逐字匹配仅作描述。null 表示不适用或未确定，不合并为失败。

| 模型群 / 前缀边界 | 响应 | 语义计算成功 | 语义立即 Final 成功 |
|---|---:|---:|---:|
| finetuned / calculate | 27 | 27/27（未定/不适用 0） | 0/27（未定/不适用 0） |
| finetuned / final | 27 | 0/27（未定/不适用 0） | 27/27（未定/不适用 0） |
| unfinetuned_base / calculate | 3 | 0/3（未定/不适用 0） | 0/3（未定/不适用 0） |
| unfinetuned_base / final | 3 | 0/3（未定/不适用 0） | 1/3（未定/不适用 0） |

### 前缀各层语义与未知分母

单元格为 true / 已确定分母；括号列出不适用或未确定。所求数量与来源表达式的判定采用固定公开参考，不能将未证明等价直接称为错误。

| 模型群 / 边界 | 语义字段 | true / 已确定 | 未定或不适用 |
|---|---|---:|---:|
| finetuned / calculate | `strict_json_object` | 27/27 | 0 |
| finetuned / calculate | `immediate_final` | 0/27 | 0 |
| finetuned / calculate | `tool_executable` | 27/27 | 0 |
| finetuned / calculate | `referenced_results_supported` | 27/27 | 0 |
| finetuned / calculate | `requested_quantity_matches_public_reference` | 27/27 | 0 |
| finetuned / calculate | `source_expression_equivalent_to_public_reference` | 27/27 | 0 |
| finetuned / calculate | `numeric_quantity_matches_public_reference` | 27/27 | 0 |
| finetuned / calculate | `final_unit_matches_request` | 0/0 | 27 |
| finetuned / calculate | `final_value_matches_supported_result` | 0/0 | 27 |
| finetuned / calculate | `final_quantity_matches_public_reference` | 0/0 | 27 |
| finetuned / calculate | `semantic_calculation_success` | 27/27 | 0 |
| finetuned / calculate | `semantic_immediate_final_success` | 0/27 | 0 |

finetuned / calculate 状态分布：`{'CALCULATION_SEMANTIC_PASS': 27}`。

| finetuned / final | `strict_json_object` | 27/27 | 0 |
| finetuned / final | `immediate_final` | 27/27 | 0 |
| finetuned / final | `tool_executable` | 0/0 | 27 |
| finetuned / final | `referenced_results_supported` | 27/27 | 0 |
| finetuned / final | `requested_quantity_matches_public_reference` | 27/27 | 0 |
| finetuned / final | `source_expression_equivalent_to_public_reference` | 27/27 | 0 |
| finetuned / final | `numeric_quantity_matches_public_reference` | 27/27 | 0 |
| finetuned / final | `final_unit_matches_request` | 27/27 | 0 |
| finetuned / final | `final_value_matches_supported_result` | 27/27 | 0 |
| finetuned / final | `final_quantity_matches_public_reference` | 27/27 | 0 |
| finetuned / final | `semantic_calculation_success` | 0/27 | 0 |
| finetuned / final | `semantic_immediate_final_success` | 27/27 | 0 |

finetuned / final 状态分布：`{'IMMEDIATE_FINAL_SEMANTIC_PASS': 27}`。

| unfinetuned_base / calculate | `strict_json_object` | 3/3 | 0 |
| unfinetuned_base / calculate | `immediate_final` | 0/3 | 0 |
| unfinetuned_base / calculate | `tool_executable` | 3/3 | 0 |
| unfinetuned_base / calculate | `referenced_results_supported` | 3/3 | 0 |
| unfinetuned_base / calculate | `requested_quantity_matches_public_reference` | 0/3 | 0 |
| unfinetuned_base / calculate | `source_expression_equivalent_to_public_reference` | 0/3 | 0 |
| unfinetuned_base / calculate | `numeric_quantity_matches_public_reference` | 0/3 | 0 |
| unfinetuned_base / calculate | `final_unit_matches_request` | 0/0 | 3 |
| unfinetuned_base / calculate | `final_value_matches_supported_result` | 0/0 | 3 |
| unfinetuned_base / calculate | `final_quantity_matches_public_reference` | 0/0 | 3 |
| unfinetuned_base / calculate | `semantic_calculation_success` | 0/3 | 0 |
| unfinetuned_base / calculate | `semantic_immediate_final_success` | 0/3 | 0 |

unfinetuned_base / calculate 状态分布：`{'TOOL_RESPONSE_SEMANTIC_FAIL_OR_UNDETERMINED': 3}`。

| unfinetuned_base / final | `strict_json_object` | 3/3 | 0 |
| unfinetuned_base / final | `immediate_final` | 2/3 | 0 |
| unfinetuned_base / final | `tool_executable` | 1/1 | 2 |
| unfinetuned_base / final | `referenced_results_supported` | 3/3 | 0 |
| unfinetuned_base / final | `requested_quantity_matches_public_reference` | 2/3 | 0 |
| unfinetuned_base / final | `source_expression_equivalent_to_public_reference` | 2/3 | 0 |
| unfinetuned_base / final | `numeric_quantity_matches_public_reference` | 2/3 | 0 |
| unfinetuned_base / final | `final_unit_matches_request` | 2/2 | 1 |
| unfinetuned_base / final | `final_value_matches_supported_result` | 1/2 | 1 |
| unfinetuned_base / final | `final_quantity_matches_public_reference` | 1/2 | 1 |
| unfinetuned_base / final | `semantic_calculation_success` | 0/3 | 0 |
| unfinetuned_base / final | `semantic_immediate_final_success` | 1/3 | 0 |

unfinetuned_base / final 状态分布：`{'IMMEDIATE_FINAL_SEMANTIC_PASS': 1, 'CONTINUED_TOOL_NOT_IMMEDIATE_FINAL': 1, 'IMMEDIATE_FINAL_SEMANTIC_FAIL_OR_UNDETERMINED': 1}`。


## 历史 R0 背景（不纳入同 R1 说明效应）

复用旧条件九个微调模型 × 同三题的 27 条已评分结果：Final 0，完整 Q 0。没有新增 R0 生成或评分。
这些历史观测只来自既有小比较摘要，不重新扫描旧会话；其运行时间和硬件占用与本轮不同，不能混入 Δ_doc。

## 每模型运行资源

下表为 worker 内实际耗时及实测峰值，不含排队，不能把十行耗时相加当总墙钟时长。

| 模型 | 预定条件顺序 | worker 秒 | 实际模型调用 | 实测保留显存峰值 GiB |
|---|---|---:|---:|---:|
| unfinetuned_base | original → gamma_doc | 549.25 | 167 | 49.020 |
| A_alpha0_11 | gamma_doc → original | 693.15 | 198 | 42.129 |
| A_plus_11 | original → gamma_doc | 791.78 | 198 | 26.586 |
| A_minus_11 | gamma_doc → original | 1485.41 | 180 | 52.678 |
| A_alpha0_29 | original → gamma_doc | 1494.52 | 182 | 26.676 |
| A_plus_29 | gamma_doc → original | 843.00 | 198 | 40.502 |
| A_minus_29 | original → gamma_doc | 1465.94 | 182 | 45.223 |
| A_alpha0_47 | gamma_doc → original | 764.18 | 198 | 45.354 |
| A_plus_47 | original → gamma_doc | 750.84 | 198 | 49.371 |
| A_minus_47 | gamma_doc → original | 2165.04 | 173 | 35.566 |

## 资源及解释边界

实际模型生成调用：1874，固定上限 1,980；实际生成 token：246176。
旧 R0 及高预算结果不重算、不回填。本轮两条件同为 R1，主对照不混入历史硬件和运行时条件差异。
三个独特任务不足以推出总体显著收益、某分布更优或 VTDO 有效/无效。基座比较只能提供条件相关的诊断线索。
来源发现、Final 恢复与完整财务合格是不同层次；Probe 提供的公开历史不能计作 Student 自主证据获取能力。
固定矩阵完成即收口：不因正例提前停止，不因零结果追加样本，不自动扩展剩余 1,593 个开发会话，也不恢复 B、确认实验、训练或改变损失。

逐任务配对值、未知/失败分母及回执见 `trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/delivery_r1_contrast_20260915/report.json`；新会话的只读观测账另保留在该运行目录 `session_ledgers/`。
