# H13_H2_01

资格：qualified。接口：H2。

模型原始字段与 SYSTEM 引用展开分别保存在每轮 response.txt / language_binding.json。
下表中的 H0/H1 子目标来自已展示候选；H2 子目标和简短理由来自模型的实际提案。

| 提交 | 类型 | 实际行为／拒绝 |
| --- | --- | --- |
| 1 | action | {"子目标": "Compute revenue growth from 2014 Q1 to 2014 Q3.", "理由": "Need revenue growth rate first. Use E1 (Q1 revenue 1594) and E2 (Q3 revenue 1717) with growth operation.", "操作": "growth", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:ca9ce1ceea0443d63f15b182b0dde8ed2385973453748d0790b9ec53ac84e28b", "role": "earlier"}, {"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:cd72687d37467085a8d5a7b6c3160c12a2a1d0fba03052e6e8cd01345af7851e", "role": "later"}], "观察": {"value": "7.716436637390213299874529486"}} |
| 2 | update | 明确接受整个观察：finance_qa_vnext_observation:c0a1758ee61db2edb8ce2980db0a6487bfbd32eeb306058ca50b4c287d8ad948 |
| 3 | action | {"子目标": "Compute operating-income growth from 2014 Q1 to 2014 Q3.", "理由": "Use the growth operation on the operating income evidence for 2014 Q1 (E3) and 2014 Q3 (E4) to calculate the percentage growth.", "操作": "growth", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:951cdd4db6f2d911bb8e948287ea6750ed13368842c54515dca744ee692a3b0d", "role": "earlier"}, {"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:5933c9e29d8219df30ba9b09e78810ca2abf926cd511bc0ad6a244bf598a845d", "role": "later"}], "观察": {"value": "7.547169811320754716981132075"}} |
| 4 | update | 明确接受整个观察：finance_qa_vnext_observation:82e278efaa7ac5f4fe7b2a8ed3cf33eb222c4da064c0945f226d9ff7a213821c |
| 5 | action | 拒绝：semantic.arity |
| 6 | action | {"子目标": "Calculate the absolute percentage-point spread between the accepted revenue growth (C1) and operating-income growth (C2).", "理由": "We have accepted two percent results: C1 (revenue growth) and C2 (operating-income growth). The task asks for the absolute percentage-point spread. Use signed_percentage_point_gap with reference C1 and observed C2 (order arbitrary; absolute gap later).", "操作": "signed_percentage_point_gap", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:fa8c093c52431a4edb6ce19a6a44ecaf4f43a138eca6d81e3f922bebc4c75508", "role": "reference_percent"}, {"kind": "claim", "ref_id": "finance_qa_vnext_claim:2f2d26c653a7fa218dc1fe60cf96ece5780fa6699b5062db9f9f1ece5815b6e0", "role": "observed_percent"}], "观察": {"unit": "percentage_points", "value": "-0.169266826069458582893397411"}} |
| 7 | update | 明确接受整个观察：finance_qa_vnext_observation:15ca9e8f8c31726726c007a9983e68e3800c92273a33848d3cd3b37ed70aa004 |
| 8 | final | 拒绝：admission.final_accepted_claim |
| 9 | final | 拒绝：admission.final_accepted_claim |
| 10 | final | 拒绝：admission.final_accepted_claim |
| 11 | final | 拒绝：admission.final_accepted_claim |
| 12 | final | 拒绝：admission.final_accepted_claim |
| 13 | final | 拒绝：admission.final_accepted_claim |
| 14 | final | 拒绝：admission.final_accepted_claim |
| 15 | final | 拒绝：admission.final_accepted_claim |
| 16 | final | 拒绝：admission.final_accepted_claim |
| 17 | final | 拒绝：admission.final_accepted_claim |
| 18 | final | 拒绝：admission.final_accepted_claim |
| 19 | final | 拒绝：admission.final_accepted_claim |
| 20 | final | 拒绝：admission.final_accepted_claim |
| 21 | final | 拒绝：admission.final_accepted_claim |
| 22 | final | 拒绝：admission.final_accepted_claim |
| 23 | final | 拒绝：admission.final_accepted_claim |
| 24 | final | 拒绝：admission.final_accepted_claim |
| 25 | final | 拒绝：admission.final_accepted_claim |
| 26 | final | 拒绝：admission.final_accepted_claim |
| 27 | action | {"子目标": "Compute the absolute percentage-point gap between C1 and C2.", "理由": "The accepted revenue growth C1 and operating-income growth C2 are both percent values over the same interval. The absolute_percentage_point_gap operation takes the signed gap from C3 and returns its absolute value in percentage_points.", "操作": "absolute_percentage_point_gap", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:181ab6ff7809b68e66421b4c0b728dd0b644d2846a3a5f3502482056a3bc851f", "role": "signed_gap"}], "观察": {"unit": "percentage_points", "value": "0.169266826069458582893397411"}} |
| 28 | update | 明确接受整个观察：finance_qa_vnext_observation:ef6592886235672a6e07d17f01bf3e8d3647ac77904166d63a60bc9fc1cbaf42 |
| 29 | final | Final 校验通过：{"answer_claim_id": "finance_qa_vnext_claim:0ff1796a0d492fc34ca5b2d504ea2bf0a0ed1d07eac8332855d8d0f80a7c7f06", "citations": ["evidence:finqa_archive_cell:ca9ce1ceea0443d63f15b182b0dde8ed2385973453748d0790b9ec53ac84e28b", "evidence:finqa_archive_cell:cd72687d37467085a8d5a7b6c3160c12a2a1d0fba03052e6e8cd01345af7851e", "evidence:finqa_archive_cell:951cdd4db6f2d911bb8e948287ea6750ed13368842c54515dca744ee692a3b0d", "evidence:finqa_archive_cell:5933c9e29d8219df30ba9b09e78810ca2abf926cd511bc0ad6a244bf598a845d"], "kind": "final", "result": {"unit": "percentage_points", "value": "0.169266826069458582893397411"}, "state_id": "finance_qa_vnext_state:b72fff29ea5ab463eda12bf1d3ce56d98eff6720d78d0805bbc9c877c6a679e4"} |

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
                "evidence": "evidence:finqa_archive_cell:ca9ce1ceea0443d63f15b182b0dde8ed2385973453748d0790b9ec53ac84e28b"
              },
              {
                "evidence": "evidence:finqa_archive_cell:cd72687d37467085a8d5a7b6c3160c12a2a1d0fba03052e6e8cd01345af7851e"
              }
            ],
            "parameters": {}
          },
          {
            "operation": "growth",
            "inputs": [
              {
                "evidence": "evidence:finqa_archive_cell:951cdd4db6f2d911bb8e948287ea6750ed13368842c54515dca744ee692a3b0d"
              },
              {
                "evidence": "evidence:finqa_archive_cell:5933c9e29d8219df30ba9b09e78810ca2abf926cd511bc0ad6a244bf598a845d"
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
  "signature": "finite_method:71ecc273fe1025daa87b5f0a76c3c5dd512da1739278943fbd138b6ce08b1308",
  "answer_lineage": [
    "evidence:finqa_archive_cell:5933c9e29d8219df30ba9b09e78810ca2abf926cd511bc0ad6a244bf598a845d",
    "evidence:finqa_archive_cell:951cdd4db6f2d911bb8e948287ea6750ed13368842c54515dca744ee692a3b0d",
    "evidence:finqa_archive_cell:ca9ce1ceea0443d63f15b182b0dde8ed2385973453748d0790b9ec53ac84e28b",
    "evidence:finqa_archive_cell:cd72687d37467085a8d5a7b6c3160c12a2a1d0fba03052e6e8cd01345af7851e"
  ],
  "used_accepted_claim_ids": [
    "finance_qa_vnext_claim:0ff1796a0d492fc34ca5b2d504ea2bf0a0ed1d07eac8332855d8d0f80a7c7f06",
    "finance_qa_vnext_claim:181ab6ff7809b68e66421b4c0b728dd0b644d2846a3a5f3502482056a3bc851f",
    "finance_qa_vnext_claim:2f2d26c653a7fa218dc1fe60cf96ece5780fa6699b5062db9f9f1ece5815b6e0",
    "finance_qa_vnext_claim:fa8c093c52431a4edb6ce19a6a44ecaf4f43a138eca6d81e3f922bebc4c75508"
  ],
  "accepted_claims_consumed_by_operations": [
    "finance_qa_vnext_claim:181ab6ff7809b68e66421b4c0b728dd0b644d2846a3a5f3502482056a3bc851f",
    "finance_qa_vnext_claim:2f2d26c653a7fa218dc1fe60cf96ece5780fa6699b5062db9f9f1ece5815b6e0",
    "finance_qa_vnext_claim:fa8c093c52431a4edb6ce19a6a44ecaf4f43a138eca6d81e3f922bebc4c75508"
  ],
  "accepted_but_unused_claim_ids": [],
  "not_a_complete_behavior_quotient": true
}
```
