# H13_H2_02

资格：qualified。接口：H2。

模型原始字段与 SYSTEM 引用展开分别保存在每轮 response.txt / language_binding.json。
下表中的 H0/H1 子目标来自已展示候选；H2 子目标和简短理由来自模型的实际提案。

| 提交 | 类型 | 实际行为／拒绝 |
| --- | --- | --- |
| 1 | action | {"子目标": "Calculate revenue growth from Q1 to Q3 using E1 and E2", "理由": "We need revenue growth first, which requires earlier (Q1) and later (Q3) revenue values. E1 is revenue for 2014 Q1 (1594) and E2 is revenue for 2014 Q3 (1717). They match metric, subject, scope, unit, currency, source, and periods are increasing.", "操作": "growth", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:ca9ce1ceea0443d63f15b182b0dde8ed2385973453748d0790b9ec53ac84e28b", "role": "earlier"}, {"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:cd72687d37467085a8d5a7b6c3160c12a2a1d0fba03052e6e8cd01345af7851e", "role": "later"}], "观察": {"value": "7.716436637390213299874529486"}} |
| 2 | update | 明确接受整个观察：finance_qa_vnext_observation:01267c51af11c0fe15a2635379200a89aa02cee8233adc8c60a9d516465498dc |
| 3 | action | {"子目标": "Calculate operating-income growth from Q1 to Q3 using E3 and E4", "理由": "We need the operating-income growth to compare with revenue growth. E3 (Q1 operating income 159) and E4 (Q3 operating income 171) are the relevant raw evidence items.", "操作": "growth", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:951cdd4db6f2d911bb8e948287ea6750ed13368842c54515dca744ee692a3b0d", "role": "earlier"}, {"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:5933c9e29d8219df30ba9b09e78810ca2abf926cd511bc0ad6a244bf598a845d", "role": "later"}], "观察": {"value": "7.547169811320754716981132075"}} |
| 4 | update | 明确接受整个观察：finance_qa_vnext_observation:a8d4618819a6f6449753e4e089b46e4da2b52aae769c2b637a8644601b22c283 |
| 5 | invalid | 拒绝：submission.schema |
| 6 | action | {"子目标": "Calculate the signed percentage-point gap between revenue growth and operating-income growth.", "理由": "Both growth percentages are accepted. Use signed_percentage_point_gap with reference_percent=C2 (operating-income growth) and observed_percent=C1 (revenue growth) to compute observed minus reference.", "操作": "signed_percentage_point_gap", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:8b6e778182e4af94387eb67c504d507fe6d61aea4c8fa211ccffd03460e8a02c", "role": "reference_percent"}, {"kind": "claim", "ref_id": "finance_qa_vnext_claim:01889722e7d2050b35c84b512cf0706289055cb40d962e84ba19ec18746f4ea2", "role": "observed_percent"}], "观察": {"unit": "percentage_points", "value": "0.169266826069458582893397411"}} |
| 7 | update | 明确接受整个观察：finance_qa_vnext_observation:d07268db0d1468b8f229da8adaa09dcbe4e78adb88560514849bbc5503f02b83 |
| 8 | action | {"子目标": "Compute the absolute percentage-point spread between revenue growth and operating-income growth.", "理由": "We have accepted C1 (revenue growth) and C2 (operating-income growth). The signed gap C3 is already accepted, but the task asks for the absolute spread. We need to apply absolute value to C3's output.", "操作": "absolute_percentage_point_gap", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:bfad6b77f13761f9768f1e2a5ca75cfcffcc09ffac8b04b20a46013c490cb2ee", "role": "signed_gap"}], "观察": {"unit": "percentage_points", "value": "0.169266826069458582893397411"}} |
| 9 | update | 明确接受整个观察：finance_qa_vnext_observation:1d2f34e1fb9285168ab3472c157dbf48f641451b20cb4d0df2c8fe333327204c |
| 10 | final | Final 校验通过：{"answer_claim_id": "finance_qa_vnext_claim:4a84524936c8cd69a6655341438ea1fdb6110da3d49c6720706811ae366c53e0", "citations": ["evidence:finqa_archive_cell:5933c9e29d8219df30ba9b09e78810ca2abf926cd511bc0ad6a244bf598a845d", "evidence:finqa_archive_cell:951cdd4db6f2d911bb8e948287ea6750ed13368842c54515dca744ee692a3b0d", "evidence:finqa_archive_cell:ca9ce1ceea0443d63f15b182b0dde8ed2385973453748d0790b9ec53ac84e28b", "evidence:finqa_archive_cell:cd72687d37467085a8d5a7b6c3160c12a2a1d0fba03052e6e8cd01345af7851e"], "kind": "final", "result": {"unit": "percentage_points", "value": "0.169266826069458582893397411"}, "state_id": "finance_qa_vnext_state:12100e0f23135a7c998e4f7502821e5f7a5cd8e04ae4388a0ec1c17f8bf35f23"} |

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
                "evidence": "evidence:finqa_archive_cell:951cdd4db6f2d911bb8e948287ea6750ed13368842c54515dca744ee692a3b0d"
              },
              {
                "evidence": "evidence:finqa_archive_cell:5933c9e29d8219df30ba9b09e78810ca2abf926cd511bc0ad6a244bf598a845d"
              }
            ],
            "parameters": {}
          },
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
          }
        ],
        "parameters": {}
      }
    ],
    "parameters": {}
  },
  "signature": "finite_method:4e6c857741ce4b3c5963cdbfc610fcb625ee551e4e12050c3aa7452c438c3c08",
  "answer_lineage": [
    "evidence:finqa_archive_cell:5933c9e29d8219df30ba9b09e78810ca2abf926cd511bc0ad6a244bf598a845d",
    "evidence:finqa_archive_cell:951cdd4db6f2d911bb8e948287ea6750ed13368842c54515dca744ee692a3b0d",
    "evidence:finqa_archive_cell:ca9ce1ceea0443d63f15b182b0dde8ed2385973453748d0790b9ec53ac84e28b",
    "evidence:finqa_archive_cell:cd72687d37467085a8d5a7b6c3160c12a2a1d0fba03052e6e8cd01345af7851e"
  ],
  "used_accepted_claim_ids": [
    "finance_qa_vnext_claim:01889722e7d2050b35c84b512cf0706289055cb40d962e84ba19ec18746f4ea2",
    "finance_qa_vnext_claim:4a84524936c8cd69a6655341438ea1fdb6110da3d49c6720706811ae366c53e0",
    "finance_qa_vnext_claim:8b6e778182e4af94387eb67c504d507fe6d61aea4c8fa211ccffd03460e8a02c",
    "finance_qa_vnext_claim:bfad6b77f13761f9768f1e2a5ca75cfcffcc09ffac8b04b20a46013c490cb2ee"
  ],
  "accepted_claims_consumed_by_operations": [
    "finance_qa_vnext_claim:01889722e7d2050b35c84b512cf0706289055cb40d962e84ba19ec18746f4ea2",
    "finance_qa_vnext_claim:8b6e778182e4af94387eb67c504d507fe6d61aea4c8fa211ccffd03460e8a02c",
    "finance_qa_vnext_claim:bfad6b77f13761f9768f1e2a5ca75cfcffcc09ffac8b04b20a46013c490cb2ee"
  ],
  "accepted_but_unused_claim_ids": [],
  "not_a_complete_behavior_quotient": true
}
```
