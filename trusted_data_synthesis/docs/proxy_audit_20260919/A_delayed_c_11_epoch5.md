# 审计后实验阶段记录

Delayed-C首次分布更新发生在真实step200，已接入第201次训练更新；随机反馈不是最终greedy成绩。

公开文件不含原始会话、模型、梯度或逐轨迹数据。实际新增调用以本阶段计量为准。

```json
{
  "schema_version": "fixed_kernel_value.v1.delayed_public_outer",
  "run": {
    "condition": "delayed_c_only",
    "key": "A_delayed_c_11",
    "pool": "A",
    "seed": 11
  },
  "actual_Student_updates_completed_at_milestone": 201,
  "random_qualified": 101,
  "denominator": 360,
  "outer_report_id": "delayed_completed_outer:8295e4a40e7dbd0f2ab0ee758cfb6ef51be8cecd2a4742789d88c0183dc29a4c",
  "numeric_guard_id": "delayed_new_point_numeric_guard:6071c1363e6de6c24b8e8cb7094e89d9bc47f45b30cb5f1523e35b6cf4b51bec",
  "novelty_term_used": false,
  "new_feedback_sessions": 360,
  "id": "delayed_public_outer:116d3c6a0f13110aad672c7d700aa2e4111cb44046b2d048447fb1a1581d3ce6"
}
```
