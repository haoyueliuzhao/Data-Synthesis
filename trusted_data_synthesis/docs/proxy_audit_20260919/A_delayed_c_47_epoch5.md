# 审计后实验阶段记录

Delayed-C首次分布更新发生在真实step200，已接入第201次训练更新；随机反馈不是最终greedy成绩。

公开文件不含原始会话、模型、梯度或逐轨迹数据。实际新增调用以本阶段计量为准。

```json
{
  "schema_version": "fixed_kernel_value.v1.delayed_public_outer",
  "run": {
    "condition": "delayed_c_only",
    "key": "A_delayed_c_47",
    "pool": "A",
    "seed": 47
  },
  "actual_Student_updates_completed_at_milestone": 201,
  "random_qualified": 104,
  "denominator": 360,
  "outer_report_id": "delayed_completed_outer:3bbc3c6bacdbe86aad78ea957817d6fd53088f1150568b301a1406a8f49ae58b",
  "numeric_guard_id": "delayed_new_point_numeric_guard:cab1fecc4d0e5f7221e0263647fefeaf8218cf98a545fc8e810a57b0afc565dc",
  "novelty_term_used": false,
  "new_feedback_sessions": 360,
  "id": "delayed_public_outer:e4f76ad5fd062cb15b2751647ab442ed051bb6a6bbed93699c2995c991335fa6"
}
```
