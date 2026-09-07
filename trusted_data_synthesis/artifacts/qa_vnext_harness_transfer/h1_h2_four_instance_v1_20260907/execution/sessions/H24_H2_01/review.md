# H24_H2_01

资格：qualified。接口：H2。

模型原始字段与 SYSTEM 引用展开分别保存在每轮 response.txt / language_binding.json。
下表中的 H0/H1 子目标来自已展示候选；H2 子目标和简短理由来自模型的实际提案。

| 提交 | 类型 | 实际行为／拒绝 |
| --- | --- | --- |
| 1 | action | {"子目标": "Calculate revenue growth from 2014 Q2 to 2014 Q4 using E1 and E2.", "理由": "Revenue growth requires earlier (Q2) and later (Q4) revenue values. E1 provides 2014 Q2 revenue 1719 million USD, E2 provides 2014 Q4 revenue 1927 million USD. They share metric, subject, scope, unit, currency, source, and periods are strictly increasing.", "操作": "growth", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:2c9d98f23788a9f71e14b8c2a5022792c8473653ddf6f076006b4cac55dc3248", "role": "earlier"}, {"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:46bfce1e3799e0f8c46406cb97049fb88da37b513f2e02c438d3e6fb171b5c9c", "role": "later"}], "观察": {"value": "12.10005817335660267597440372"}} |
| 2 | update | 明确接受整个观察：finance_qa_vnext_observation:59ef23f6b6badde0e51eb73ebe268861d7a9603384f0c2efba48311b352b7f3e |
| 3 | action | {"子目标": "Calculate operating-income growth from 2014 Q2 to 2014 Q4 using E3 and E4.", "理由": "We need operating-income growth to compute the absolute percentage-point spread against the already accepted revenue growth (C1). E3 and E4 are raw monetary evidence items for operating income in 2014 Q2 and 2014 Q4 respectively.", "操作": "growth", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:94f86fa2432b68177c157e1e71f46a1d9a60971989a2a7c92622e3e4ea5cd153", "role": "earlier"}, {"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:ccd49ee8d862ad04084ab6cd20612cc3364d8c1ebc290c14e7e537eb7b8f160b", "role": "later"}], "观察": {"value": "-20.44198895027624309392265193"}} |
| 4 | update | 明确接受整个观察：finance_qa_vnext_observation:cf2907a51a2683a8b8fed6a3902d2363583a3f8889fc5521ca016cf129aca8a5 |
| 5 | action | {"子目标": "Compute the signed percentage-point gap between revenue growth (C1) and operating-income growth (C2).", "理由": "The question asks for the absolute percentage-point spread between the two growth rates. The signed_percentage_point_gap operation accepts two percent results and outputs observed minus reference. Using revenue growth as reference and operating-income growth as observed gives the signed gap, then absolute_percentage_point_gap yields the final spread.", "操作": "signed_percentage_point_gap", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:2132a3ee999efc1aa170a44adfd7f39fc40886629406e9ca0bbce170ef960ada", "role": "reference_percent"}, {"kind": "claim", "ref_id": "finance_qa_vnext_claim:9874c9160a502c27658d2bbb3787c47710ec24b319230db1fae9c38a3c995f30", "role": "observed_percent"}], "观察": {"unit": "percentage_points", "value": "-32.54204712363284576989705565"}} |
| 6 | update | 明确接受整个观察：finance_qa_vnext_observation:cb8a776f3e445d1bb543b9e03340d3a8f71451958b40703f6cc953d24dbf80e8 |
| 7 | action | {"子目标": "Take the absolute value of the signed percentage-point gap C3.", "理由": "The question asks for the absolute percentage-point spread. C3 is the signed gap between revenue growth and operating-income growth; applying absolute_percentage_point_gap to C3 yields the required non-negative percentage_points result.", "操作": "absolute_percentage_point_gap", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:2a5299dc67c048ab6fb12f4d0e1c0b5ae0fcfc429d8cd1570dcf560c80af525f", "role": "signed_gap"}], "观察": {"unit": "percentage_points", "value": "32.54204712363284576989705565"}} |
| 8 | update | 明确接受整个观察：finance_qa_vnext_observation:f32641eb55ef029eed610f3e1fc9432598df43a489dee2897f3b2f60335b749f |
| 9 | final | Final 校验通过：{"answer_claim_id": "finance_qa_vnext_claim:f88c3a751ff9cf2056ac084b21b9c44767d7190fdc871d2ef6ee7e0cacf7218a", "citations": ["evidence:finqa_archive_cell:2c9d98f23788a9f71e14b8c2a5022792c8473653ddf6f076006b4cac55dc3248", "evidence:finqa_archive_cell:46bfce1e3799e0f8c46406cb97049fb88da37b513f2e02c438d3e6fb171b5c9c", "evidence:finqa_archive_cell:94f86fa2432b68177c157e1e71f46a1d9a60971989a2a7c92622e3e4ea5cd153", "evidence:finqa_archive_cell:ccd49ee8d862ad04084ab6cd20612cc3364d8c1ebc290c14e7e537eb7b8f160b"], "kind": "final", "result": {"unit": "percentage_points", "value": "32.54204712363284576989705565"}, "state_id": "finance_qa_vnext_state:09a848c15edddbcdf5cd973fdf38d009813ba5736815bf68545409025a4149dc"} |

## 实际 Final 支持图（不是完整行为商）

```json
{
  "tree": {
    "operation": "absolute_percentage_point_gap",
    "inputs": [
      {
        "operation": "signed_percentage_point_gap",
        "inputs": [
          {
            "operation": "growth",
            "inputs": [
              {
                "evidence": "evidence:finqa_archive_cell:2c9d98f23788a9f71e14b8c2a5022792c8473653ddf6f076006b4cac55dc3248"
              },
              {
                "evidence": "evidence:finqa_archive_cell:46bfce1e3799e0f8c46406cb97049fb88da37b513f2e02c438d3e6fb171b5c9c"
              }
            ],
            "parameters": {}
          },
          {
            "operation": "growth",
            "inputs": [
              {
                "evidence": "evidence:finqa_archive_cell:94f86fa2432b68177c157e1e71f46a1d9a60971989a2a7c92622e3e4ea5cd153"
              },
              {
                "evidence": "evidence:finqa_archive_cell:ccd49ee8d862ad04084ab6cd20612cc3364d8c1ebc290c14e7e537eb7b8f160b"
              }
            ],
            "parameters": {}
          }
        ],
        "parameters": {}
      }
    ],
    "parameters": {}
  },
  "signature": "finite_method:f943543e6dab58010fde9964130b7204496f32798e13b5395b24a7893b70bad8",
  "answer_lineage": [
    "evidence:finqa_archive_cell:2c9d98f23788a9f71e14b8c2a5022792c8473653ddf6f076006b4cac55dc3248",
    "evidence:finqa_archive_cell:46bfce1e3799e0f8c46406cb97049fb88da37b513f2e02c438d3e6fb171b5c9c",
    "evidence:finqa_archive_cell:94f86fa2432b68177c157e1e71f46a1d9a60971989a2a7c92622e3e4ea5cd153",
    "evidence:finqa_archive_cell:ccd49ee8d862ad04084ab6cd20612cc3364d8c1ebc290c14e7e537eb7b8f160b"
  ],
  "used_accepted_claim_ids": [
    "finance_qa_vnext_claim:2132a3ee999efc1aa170a44adfd7f39fc40886629406e9ca0bbce170ef960ada",
    "finance_qa_vnext_claim:2a5299dc67c048ab6fb12f4d0e1c0b5ae0fcfc429d8cd1570dcf560c80af525f",
    "finance_qa_vnext_claim:9874c9160a502c27658d2bbb3787c47710ec24b319230db1fae9c38a3c995f30",
    "finance_qa_vnext_claim:f88c3a751ff9cf2056ac084b21b9c44767d7190fdc871d2ef6ee7e0cacf7218a"
  ],
  "accepted_claims_consumed_by_operations": [
    "finance_qa_vnext_claim:2132a3ee999efc1aa170a44adfd7f39fc40886629406e9ca0bbce170ef960ada",
    "finance_qa_vnext_claim:2a5299dc67c048ab6fb12f4d0e1c0b5ae0fcfc429d8cd1570dcf560c80af525f",
    "finance_qa_vnext_claim:9874c9160a502c27658d2bbb3787c47710ec24b319230db1fae9c38a3c995f30"
  ],
  "accepted_but_unused_claim_ids": [],
  "not_a_complete_behavior_quotient": true
}
```
