# 审计后实验阶段记录

资源调度修订后完成。有效剂量仍为每种子400步，最终每种子固定180条；中断会话的额外生成尝试独立记账。原103步重放保留，未把有效剂量当作物理计算总量；未新增随机反馈、未重评已封存反馈、未启动B或确认。

公开文件不含原始会话、模型、梯度或逐轨迹数据。实际新增调用以本阶段计量为准。

```json
{
  "schema_version": "fixed_kernel_value.v1.delayed_C_recovered_matrix",
  "status": "COMPLETE_THREE_DELAYED_C_RUNS_AFTER_RECOVERY",
  "recovery_plan_id": "delayed_C_recovery_plan:2248bdf67dab199b0b97a818e5fad51895524913ff89c1702d3d24c11a6864d9",
  "resource_amendment_id": "delayed_C_aggressive_autorun:35d514700597ec2b5eaf4544038eb81351dc65a373a0a3a9babd224c2d8fbbcd",
  "original_plan_id": "delayed_C_registered_plan:b632bc2cdcfe0ed9b3470e2c0efc3bf64c007a7adbfe0f5f4d93cbc4655ddd04",
  "Delayed_C_qualified": 176,
  "Static_qualified": 170,
  "original_C_only_qualified": 155,
  "original_Full_qualified": 153,
  "denominator_per_condition": 540,
  "primary_mean_difference": 0.011111111111111112,
  "primary_direction": "POSITIVE_FIXED_DEV_DELAYED_DIRECTION",
  "effective_optimizer_updates": 1200,
  "physical_completed_optimizer_updates_lower_bound": 1303,
  "physical_exact_count_not_claimed": true,
  "known_additional_repeated_completed_updates": 0,
  "interrupted_update_intents_with_unknown_completion_count": 0,
  "interrupted_final_generate_call_upper_bound": 0,
  "new_feedback_sessions": 0,
  "original_resource_failure_preserved": true,
  "development_is_not_independent_confirmation": true,
  "B_or_confirmation_started": false,
  "no_Full_or_Novelty_success_relabel": true,
  "runs": [
    {
      "run": {
        "condition": "delayed_c_only",
        "key": "A_delayed_c_11",
        "pool": "A",
        "seed": 11
      },
      "qualified": 66,
      "report_id": "delayed_C_run_report:efaaf24884a6dc858d29131d2d7872014a416f79fd98d215df0b4d06f9fa9c87"
    },
    {
      "run": {
        "condition": "delayed_c_only",
        "key": "A_delayed_c_47",
        "pool": "A",
        "seed": 47
      },
      "qualified": 51,
      "report_id": "delayed_C_recovered_run:a9885fbbfd9a25b20f177250463c992d122f3268c5014a11af7dafcd8e7a8d1b"
    },
    {
      "run": {
        "condition": "delayed_c_only",
        "key": "A_delayed_c_29",
        "pool": "A",
        "seed": 29
      },
      "qualified": 59,
      "report_id": "delayed_C_recovered_run:19f6310105324ba73d3237e665fd7a158a2773f44a30d02c8bc646de5741ee91"
    }
  ],
  "at": "2026-09-22T11:26:06.282059+00:00",
  "id": "delayed_C_recovered_matrix:3beabcba5e1bfd94d82789cd840e4b807877bb903ecd0f1b726ea1978f171bde"
}
```
