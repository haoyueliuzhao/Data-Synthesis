# 审计后实验阶段记录

Delayed-C唯一epoch10最终检查点；主比较仍为Static。该开发集参与元优化，不是独立确认，也不改写旧Full结果。

公开文件不含原始会话、模型、梯度或逐轨迹数据。实际新增调用以本阶段计量为准。

```json
{
  "actual_generate_calls": 8817,
  "actual_optimizer_updates": 400,
  "at": "2026-09-20T20:25:16.947656+00:00",
  "denominator": 180,
  "elapsed_seconds": 101898.08986569988,
  "feedback_sessions": 360,
  "final_assessment_report_id": "anchored_independent_scoring:81c83fd0e1db073da2af7a85772122ba1acba39d1f720c627d7ebaea8e2774f2",
  "final_greedy_sessions": 180,
  "final_point_id": "anchored_model_parameter_point:5ff2b988d6bc159ec34558d50a4f916621ec7e68d4e56bffaa1089fb10ed927b",
  "final_qualified": 66,
  "id": "delayed_C_run_report:efaaf24884a6dc858d29131d2d7872014a416f79fd98d215df0b4d06f9fa9c87",
  "outer_report_id": "delayed_completed_outer:8295e4a40e7dbd0f2ab0ee758cfb6ef51be8cecd2a4742789d88c0183dc29a4c",
  "plan_id": "delayed_C_registered_plan:b632bc2cdcfe0ed9b3470e2c0efc3bf64c007a7adbfe0f5f4d93cbc4655ddd04",
  "run": {
    "condition": "delayed_c_only",
    "key": "A_delayed_c_11",
    "pool": "A",
    "seed": 11
  },
  "schema_version": "fixed_kernel_value.v1.delayed_C_run_report",
  "status": "COMPLETE_FIXED_FINAL"
}
```
