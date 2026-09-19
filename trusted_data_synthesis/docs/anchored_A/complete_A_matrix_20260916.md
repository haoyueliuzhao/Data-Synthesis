# 已登记anchored A阶段记录

自动生成的汇总；原始会话、模型和梯度张量留在本地。

随机反馈效用不等于最终greedy效用。dev已参与元优化，不是独立确认。Full是唯一主候选，B/确认仍关闭。

```json
{
  "plan_id": "anchored_registered_A_plan:a48f25774415bafa7f1fcbfdce72de51aebcbb1df3b320d37af2bdebba31f9b1",
  "status": "COMPLETE_SIX_NEW_A_RUNS",
  "runs": [
    {
      "run": {
        "condition": "full_anchored_vtdo",
        "key": "A_full_11",
        "pool": "A",
        "seed": 11
      },
      "id": "anchored_A_run_report:5994c32beb2406ddb921cdd3f0e0a4925c99d4d7e6f5c43292ebf1a7d62c46a2",
      "final_qualified": 60,
      "denominator": 180,
      "actual_generate_calls": 11550
    },
    {
      "run": {
        "condition": "c_only_anchored",
        "key": "A_c_only_11",
        "pool": "A",
        "seed": 11
      },
      "id": "anchored_A_run_report:62112d2bf576da27ad73d00241aeb8dde2415177b5adb421e97047c688ebd7ca",
      "final_qualified": 62,
      "denominator": 180,
      "actual_generate_calls": 11513
    },
    {
      "run": {
        "condition": "full_anchored_vtdo",
        "key": "A_full_29",
        "pool": "A",
        "seed": 29
      },
      "id": "anchored_A_run_report:5d537e3e472fb6b202614e509dbe92b428ddb12dd49d47334636967effe95c31",
      "final_qualified": 48,
      "denominator": 180,
      "actual_generate_calls": 12209
    },
    {
      "run": {
        "condition": "c_only_anchored",
        "key": "A_c_only_29",
        "pool": "A",
        "seed": 29
      },
      "id": "anchored_A_run_report:a06086868698b50d7d238371b45ab22d1f58ef902f167b945dc2667bebc3bf9d",
      "final_qualified": 45,
      "denominator": 180,
      "actual_generate_calls": 12140
    },
    {
      "run": {
        "condition": "full_anchored_vtdo",
        "key": "A_full_47",
        "pool": "A",
        "seed": 47
      },
      "id": "anchored_A_run_report:c735a9f390dd8973da2836426f6bedb45be8d2b447ed341b50e031a0fedc2943",
      "final_qualified": 45,
      "denominator": 180,
      "actual_generate_calls": 11731
    },
    {
      "run": {
        "condition": "c_only_anchored",
        "key": "A_c_only_47",
        "pool": "A",
        "seed": 47
      },
      "id": "anchored_A_run_report:23243751545468acc43f4f859568528b882c5a9e01f3e1183ec13df89de26280",
      "final_qualified": 48,
      "denominator": 180,
      "actual_generate_calls": 11600
    }
  ],
  "B_or_confirmation_started": false,
  "no_C_only_candidate_substitution": true,
  "Static_qualified": 170,
  "Full_qualified": 153,
  "C_only_qualified": 155,
  "denominator_per_condition": 540,
  "primary_mean_difference": -0.03148148148148148,
  "primary_direction": "RETAIN_STATIC_NO_POSITIVE_FULL_DIRECTION",
  "at": "2026-09-19T00:31:11.044161+00:00",
  "source_report_id": "anchored_A_complete_matrix:bd736f023225a1e967cf1c13e96bd530f827da183afbf03d78e3461d4e2759b9"
}
```
