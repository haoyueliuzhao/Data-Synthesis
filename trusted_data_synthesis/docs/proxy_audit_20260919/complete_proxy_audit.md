# 审计后实验阶段记录

原负结果保留；数值门通过才准入已登记Delayed-C。repeat交叉分数是同固定点Monte Carlo诊断，不是独立泛化或已取得训练收益。

公开文件不含原始会话、模型、梯度或逐轨迹数据。实际新增调用以本阶段计量为准。

```json
{
  "schema_version": "fixed_kernel_value.v1.anchored_proxy_audit_report",
  "plan_id": "anchored_proxy_audit_plan:aa6922cd9f06d2755c65312abd8a7b8302c3f85acd2a1e677f3ce91ec6353df6",
  "status": "PASS_AS_SCOPED_READY_FOR_DELAYED_C",
  "all_twelve_numeric_points_passed": true,
  "direction_audit_completed": true,
  "direction_stability_not_assumed": true,
  "points": [
    {
      "key": "A_c_only_11_epoch0",
      "numeric_passed": true,
      "C_relative_weighted_RMS": 4.0066030068833737e-07,
      "pi_reference_TV": 5.926056160570834e-09,
      "cross": {
        "S_1_to_2": -0.0009267049801589489,
        "S_2_to_1": -0.0004355376810777129,
        "interpretable": true,
        "one_or_both_halves_zero_not_regrouped": false
      },
      "leave_one_out": {
        "max_pi_TV_change": 0.014199141357493127,
        "max_relative_C_change": 0.840064858434166,
        "min_full_C_cosine": 0.556932777152284,
        "positive_terms": 5
      }
    },
    {
      "key": "A_full_11_epoch0",
      "numeric_passed": true,
      "C_relative_weighted_RMS": 4.0066030068833737e-07,
      "pi_reference_TV": 5.926056163250981e-09,
      "cross": {
        "S_1_to_2": -0.0009267049801589488,
        "S_2_to_1": -0.00043553768107771295,
        "interpretable": true,
        "one_or_both_halves_zero_not_regrouped": false
      },
      "leave_one_out": {
        "max_pi_TV_change": 0.014199141357493127,
        "max_relative_C_change": 0.840064858434166,
        "min_full_C_cosine": 0.556932777152284,
        "positive_terms": 5
      }
    },
    {
      "key": "A_c_only_11_epoch5",
      "numeric_passed": true,
      "C_relative_weighted_RMS": 3.558280713067918e-08,
      "pi_reference_TV": 8.338163908459816e-11,
      "cross": {
        "S_1_to_2": 8.778582771982451e-05,
        "S_2_to_1": 5.338510641494348e-05,
        "interpretable": true,
        "one_or_both_halves_zero_not_regrouped": false
      },
      "leave_one_out": {
        "max_pi_TV_change": 0.0051487714969781434,
        "max_relative_C_change": 0.4078638595062879,
        "min_full_C_cosine": 0.9172063882333995,
        "positive_terms": 97
      }
    },
    {
      "key": "A_full_11_epoch5",
      "numeric_passed": true,
      "C_relative_weighted_RMS": 3.558280713662964e-08,
      "pi_reference_TV": 8.33576595336144e-11,
      "cross": {
        "S_1_to_2": 9.714658408810252e-05,
        "S_2_to_1": 5.5940367559131714e-05,
        "interpretable": true,
        "one_or_both_halves_zero_not_regrouped": false
      },
      "leave_one_out": {
        "max_pi_TV_change": 0.005146734571897039,
        "max_relative_C_change": 0.4078638595062879,
        "min_full_C_cosine": 0.9172063882333993,
        "positive_terms": 97
      }
    },
    {
      "key": "A_c_only_29_epoch0",
      "numeric_passed": true,
      "C_relative_weighted_RMS": 2.853334736559035e-07,
      "pi_reference_TV": 4.1097788076698005e-09,
      "cross": {
        "S_1_to_2": -0.000277602775045232,
        "S_2_to_1": -0.0001787659555793071,
        "interpretable": true,
        "one_or_both_halves_zero_not_regrouped": false
      },
      "leave_one_out": {
        "max_pi_TV_change": 0.0199559520394438,
        "max_relative_C_change": 1.0773058180747033,
        "min_full_C_cosine": 0.1960330794897844,
        "positive_terms": 5
      }
    },
    {
      "key": "A_full_29_epoch0",
      "numeric_passed": true,
      "C_relative_weighted_RMS": 2.853334736559035e-07,
      "pi_reference_TV": 4.109778809456566e-09,
      "cross": {
        "S_1_to_2": -0.000277602775045232,
        "S_2_to_1": -0.00017876595557930712,
        "interpretable": true,
        "one_or_both_halves_zero_not_regrouped": false
      },
      "leave_one_out": {
        "max_pi_TV_change": 0.01995595203944381,
        "max_relative_C_change": 1.0773058180747033,
        "min_full_C_cosine": 0.1960330794897844,
        "positive_terms": 5
      }
    },
    {
      "key": "A_c_only_29_epoch5",
      "numeric_passed": true,
      "C_relative_weighted_RMS": 3.856835073818575e-08,
      "pi_reference_TV": 1.123757454712243e-10,
      "cross": {
        "S_1_to_2": -0.0004721226931085888,
        "S_2_to_1": -0.0006517255241409968,
        "interpretable": true,
        "one_or_both_halves_zero_not_regrouped": false
      },
      "leave_one_out": {
        "max_pi_TV_change": 0.004139849782975189,
        "max_relative_C_change": 0.38055489929097,
        "min_full_C_cosine": 0.9266675593241874,
        "positive_terms": 102
      }
    },
    {
      "key": "A_full_29_epoch5",
      "numeric_passed": true,
      "C_relative_weighted_RMS": 3.856835074206337e-08,
      "pi_reference_TV": 1.124340495792936e-10,
      "cross": {
        "S_1_to_2": -0.0004650737346281537,
        "S_2_to_1": -0.0006622755170917587,
        "interpretable": true,
        "one_or_both_halves_zero_not_regrouped": false
      },
      "leave_one_out": {
        "max_pi_TV_change": 0.004141894599910105,
        "max_relative_C_change": 0.38055489929097,
        "min_full_C_cosine": 0.9266675593241874,
        "positive_terms": 102
      }
    },
    {
      "key": "A_c_only_47_epoch0",
      "numeric_passed": true,
      "C_relative_weighted_RMS": 1.6818022776511805e-06,
      "pi_reference_TV": 2.270676246349246e-08,
      "cross": {
        "S_1_to_2": -2.610119385353268e-05,
        "S_2_to_1": -2.4921372616820724e-05,
        "interpretable": true,
        "one_or_both_halves_zero_not_regrouped": false
      },
      "leave_one_out": {
        "max_pi_TV_change": 0.009286488962153587,
        "max_relative_C_change": 0.6365279630786447,
        "min_full_C_cosine": 0.7984757932123869,
        "positive_terms": 8
      }
    },
    {
      "key": "A_full_47_epoch0",
      "numeric_passed": true,
      "C_relative_weighted_RMS": 1.6818022776511805e-06,
      "pi_reference_TV": 2.2706762461376096e-08,
      "cross": {
        "S_1_to_2": -2.61011938535327e-05,
        "S_2_to_1": -2.4921372616820737e-05,
        "interpretable": true,
        "one_or_both_halves_zero_not_regrouped": false
      },
      "leave_one_out": {
        "max_pi_TV_change": 0.009286488962153592,
        "max_relative_C_change": 0.6365279630786447,
        "min_full_C_cosine": 0.7984757932123869,
        "positive_terms": 8
      }
    },
    {
      "key": "A_c_only_47_epoch5",
      "numeric_passed": true,
      "C_relative_weighted_RMS": 3.787955324601429e-08,
      "pi_reference_TV": 7.279177552388384e-11,
      "cross": {
        "S_1_to_2": 0.0001576910649684179,
        "S_2_to_1": 0.00014854372355078022,
        "interpretable": true,
        "one_or_both_halves_zero_not_regrouped": false
      },
      "leave_one_out": {
        "max_pi_TV_change": 0.0017976540692218334,
        "max_relative_C_change": 0.19916278536918897,
        "min_full_C_cosine": 0.9902407319359953,
        "positive_terms": 109
      }
    },
    {
      "key": "A_full_47_epoch5",
      "numeric_passed": true,
      "C_relative_weighted_RMS": 3.787955326445244e-08,
      "pi_reference_TV": 7.2871447461334e-11,
      "cross": {
        "S_1_to_2": 0.00015019793714966836,
        "S_2_to_1": 0.00014339500301684244,
        "interpretable": true,
        "one_or_both_halves_zero_not_regrouped": false
      },
      "leave_one_out": {
        "max_pi_TV_change": 0.001802413674132228,
        "max_relative_C_change": 0.19916278536918894,
        "min_full_C_cosine": 0.990240731935995,
        "positive_terms": 109
      }
    }
  ],
  "actual_extra_resources": {
    "extra_class_passes": 6,
    "extra_class_sequence_tokens": 107653794,
    "replayed_trajectories": 326,
    "replayed_responses": 1863,
    "replayed_output_tokens": 83173,
    "cached_forward_target_positions": 166346
  },
  "new_generated_sessions": 0,
  "new_financial_scores": 0,
  "B_and_confirmation": 0,
  "at": "2026-09-19T16:06:34.180043+00:00",
  "id": "anchored_proxy_audit_report:75713ce5b48d23e831095f7faa2e0bf162f19a39ae60e33d3d01b4962fb8081c"
}
```
