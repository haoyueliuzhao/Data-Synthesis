# 审计后实验阶段记录

按用户2026-09-21恢复指令登记资源故障修复：复用本次实验step200的参数、Adam和RNG。保留seed11完成结果及原失败记录；不重新采样或评分720条反馈。seed47的201—303步需重放，103步重复计算独立记账；有效剂量仍为每种子400步。该恢复修订不是声称原1200步物理预算未超出，也不是重新筛选种子。

公开文件不含原始会话、模型、梯度或逐轨迹数据。实际新增调用以本阶段计量为准。

```json
{
  "schema_version": "fixed_kernel_value.v1.delayed_C_recovery_public_registration",
  "plan_id": "delayed_C_recovery_plan:2248bdf67dab199b0b97a818e5fad51895524913ff89c1702d3d24c11a6864d9",
  "parent_plan_id": "delayed_C_registered_plan:b632bc2cdcfe0ed9b3470e2c0efc3bf64c007a7adbfe0f5f4d93cbc4655ddd04",
  "failure_id": "delayed_C_coordinator_failure:31c8a7bf0d1672c4b6ac7e54b7e78761fbc320ae5d208788f97bfafb90601bdf",
  "budget": {
    "original_completed_optimizer_updates": 903,
    "resumed_optimizer_updates": 400,
    "repeated_completed_optimizer_updates": 103,
    "cumulative_completed_optimizer_updates": 1303,
    "effective_final_optimizer_updates": 1200,
    "original_partial_step304_optimizer_updates": 0,
    "new_feedback_sessions": 0,
    "new_private_feedback_scores": 0,
    "reused_feedback_sessions": 720,
    "new_final_greedy_sessions": 360,
    "new_final_generate_call_cap": 11520,
    "extra_successful_class_passes": 1,
    "maximum_class_pass_attempts": 3,
    "repeated_original_feedback_responses": 58,
    "required_seed29_feedback_responses": 631,
    "maximum_resource_failures_per_run": 3,
    "B_and_confirmation": 0
  },
  "resumed_seeds": [
    47,
    29
  ],
  "original_sources_unchanged": true,
  "registration_before_recovery_GPU_work": true,
  "id": "delayed_C_recovery_public_registration:56d80233972846a2fbfb7b8e7393d1c0874deec0c44e03450b9ded4a9e217b65"
}
```
