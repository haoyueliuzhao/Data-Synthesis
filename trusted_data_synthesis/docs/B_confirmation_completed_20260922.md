# B 材料主确认完成

Static 与 Delayed-C 共用各 seed 的真实 step200 参数、Adam 和 RNG；六模型均有效400步。720确认题不参与反馈或选择。预登记主判据为 CIK 配对区间下界严格大于0；跨零只表示未确认，不表示等效。固定三个训练种子的来源聚类区间不覆盖全部训练随机性。

完整逐项分析及资源账本保存在已注册数据盘目录，公开记录仅含聚合数据。

```json
{
  "A_auxiliary_sessions": 0,
  "B_final_dev_sessions": 0,
  "at": "2026-09-25T15:49:32.628174+00:00",
  "attempted_generate_call_upper_bound": 80081,
  "ci95": {
    "lower": -0.005401467014707668,
    "lower_rational": "-4146017/767572400",
    "upper": 0.019544733184282456,
    "upper_rational": "14090483/720935040"
  },
  "confirmation_sessions": 4320,
  "effective_model_updates": 2400,
  "fixed_seed_source_cluster_interval_not_all_training_randomness": true,
  "id": "B_confirm_completed_study:a28ceede5c5da1da4f502bb94954aa615bebeb9598e77c87c6188404d4cc4b77",
  "models": [
    {
      "condition": "static",
      "denominator": 720,
      "key": "B_static_11",
      "qualified": 254,
      "scoring_report_id": "anchored_independent_scoring:0f0fd07e59ce97a4ac454e8da4fae96820fbe4b1110654aa7c46e01dfc47cabc",
      "seed": 11
    },
    {
      "condition": "delayed_c",
      "denominator": 720,
      "key": "B_delayed_c_11",
      "qualified": 291,
      "scoring_report_id": "anchored_independent_scoring:a358fedddabd01e1828da04182b605e785b04beb115ac60b57e9fb9949601107",
      "seed": 11
    },
    {
      "condition": "static",
      "denominator": 720,
      "key": "B_static_29",
      "qualified": 245,
      "scoring_report_id": "anchored_independent_scoring:67f0db87e03bc752d8f9cfadad974898356a0470d4474dd2c7022e982a9fde40",
      "seed": 29
    },
    {
      "condition": "delayed_c",
      "denominator": 720,
      "key": "B_delayed_c_29",
      "qualified": 218,
      "scoring_report_id": "anchored_independent_scoring:d740fcb9296a7c58cfbcf714fda2af0879932280d51fbdcc0cbef7a5cf98de4b",
      "seed": 29
    },
    {
      "condition": "static",
      "denominator": 720,
      "key": "B_static_47",
      "qualified": 235,
      "scoring_report_id": "anchored_independent_scoring:68581778861e226899de8dac50fae5190b454ee4584e323be1ac66efb5613710",
      "seed": 47
    },
    {
      "condition": "delayed_c",
      "denominator": 720,
      "key": "B_delayed_c_47",
      "qualified": 240,
      "scoring_report_id": "anchored_independent_scoring:785fafb86085089f6295884e6556c2623e3355726bb644b684de2913898d53db",
      "seed": 47
    }
  ],
  "new_feedback_sessions": 1080,
  "no_candidate_switch": true,
  "planned_physical_updates_base": 1800,
  "point_estimate": 0.006944444444444444,
  "positive_effect_confirmed": false,
  "primary": "B Delayed-C minus B Static",
  "protocol_id": "B_confirm_protocol:0dba5b5625fbf37d7e4f93fc0b7636cba1df66a1fec611e6af67d6a5710bbe1a",
  "reserved_physical_optimizer_attempts": 1800,
  "schema_version": "fixed_kernel_value.v1.B_confirm_completed_study",
  "status": "COMPLETE_B_MAIN_CONFIRMATION"
}
```
