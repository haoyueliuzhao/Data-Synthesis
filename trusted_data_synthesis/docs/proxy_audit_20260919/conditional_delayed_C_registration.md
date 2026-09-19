# 审计后实验阶段记录

这是新的、条件准入的三种子Delayed-C登记。协调器等待完整代理审计通过；当前未启动训练，前五遍必须保持Static，原400步剂量不增加。

公开文件不含原始会话、模型、梯度或逐轨迹数据。实际新增调用以本阶段计量为准。

```json
{
  "B_and_confirmation": 0,
  "fresh_full_400_steps": true,
  "id": "delayed_C_public_registration:1dfec802d2c008037506fd95ca016c109d2e0d5fbf0a30c008061bbf083841b8",
  "new_feedback_sessions": 1080,
  "new_final_greedy_sessions": 540,
  "new_generate_cap": 51840,
  "new_optimizer_updates": 1200,
  "new_training_runs": 3,
  "outer_steps": [
    200
  ],
  "plan_id": "delayed_C_registered_plan:b632bc2cdcfe0ed9b3470e2c0efc3bf64c007a7adbfe0f5f4d93cbc4655ddd04",
  "primary_comparison": "Delayed-C minus Static",
  "required_proxy_audit_plan_id": "anchored_proxy_audit_plan:aa6922cd9f06d2755c65312abd8a7b8302c3f85acd2a1e677f3ce91ec6353df6",
  "runs": [
    {
      "condition": "delayed_c_only",
      "key": "A_delayed_c_11",
      "pool": "A",
      "seed": 11
    },
    {
      "condition": "delayed_c_only",
      "key": "A_delayed_c_29",
      "pool": "A",
      "seed": 29
    },
    {
      "condition": "delayed_c_only",
      "key": "A_delayed_c_47",
      "pool": "A",
      "seed": 47
    }
  ],
  "schema_version": "fixed_kernel_value.v1.delayed_C_public_registration",
  "training_started": false
}
```
