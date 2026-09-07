# H13_H1_02

资格：qualified。接口：H1。

模型原始字段与 SYSTEM 引用展开分别保存在每轮 response.txt / language_binding.json。
下表中的 H0/H1 子目标来自已展示候选；H2 子目标和简短理由来自模型的实际提案。

| 提交 | 类型 | 实际行为／拒绝 |
| --- | --- | --- |
| 1 | action | {"子目标": "resolve_evidence", "理由": null, "操作": "lookup", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:ca9ce1ceea0443d63f15b182b0dde8ed2385973453748d0790b9ec53ac84e28b", "role": "evidence_role_1", "selector": null}], "观察": {"payload": {"currency": "USD", "kind": "scalar_observation", "unit": "million USD", "value": "1594"}, "selected_ref": "evidence:finqa_archive_cell:ca9ce1ceea0443d63f15b182b0dde8ed2385973453748d0790b9ec53ac84e28b"}} |
| 2 | update | 明确接受整个观察：finance_qa_vnext_observation:5ab759ca005843650d8834c4c3331e4bf5f9454766b6167d2870967eec215e70 |
| 3 | action | {"子目标": "resolve_evidence", "理由": null, "操作": "lookup", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:cd72687d37467085a8d5a7b6c3160c12a2a1d0fba03052e6e8cd01345af7851e", "role": "evidence_role_2", "selector": null}], "观察": {"payload": {"currency": "USD", "kind": "scalar_observation", "unit": "million USD", "value": "1717"}, "selected_ref": "evidence:finqa_archive_cell:cd72687d37467085a8d5a7b6c3160c12a2a1d0fba03052e6e8cd01345af7851e"}} |
| 4 | update | 明确接受整个观察：finance_qa_vnext_observation:052835ed82dd2c2de0aef443e4e960a2c7f5d0868d07a3845a784c0910dffc86 |
| 5 | action | {"子目标": "resolve_evidence", "理由": null, "操作": "lookup", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:951cdd4db6f2d911bb8e948287ea6750ed13368842c54515dca744ee692a3b0d", "role": "evidence_role_3", "selector": null}], "观察": {"payload": {"currency": "USD", "kind": "scalar_observation", "unit": "million USD", "value": "159"}, "selected_ref": "evidence:finqa_archive_cell:951cdd4db6f2d911bb8e948287ea6750ed13368842c54515dca744ee692a3b0d"}} |
| 6 | update | 明确接受整个观察：finance_qa_vnext_observation:74f2a4486a2bd21e2ec5de31a757a1ab16238781ff1a6fa47a12e841642f388d |
| 7 | action | {"子目标": "resolve_evidence", "理由": null, "操作": "lookup", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:5933c9e29d8219df30ba9b09e78810ca2abf926cd511bc0ad6a244bf598a845d", "role": "evidence_role_4", "selector": null}], "观察": {"payload": {"currency": "USD", "kind": "scalar_observation", "unit": "million USD", "value": "171"}, "selected_ref": "evidence:finqa_archive_cell:5933c9e29d8219df30ba9b09e78810ca2abf926cd511bc0ad6a244bf598a845d"}} |
| 8 | update | 明确接受整个观察：finance_qa_vnext_observation:bb4d9ebd49c6136f5a84565aeddcb469343b8da6039f75594a0b874e16f32c9c |
| 9 | action | {"子目标": "derive_quantity", "理由": null, "操作": "growth", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:7e70c296381e9481137d08f8793ffb16341632daca6e8f5337ecff68b37fa665", "role": "revenue_earlier_value", "selector": "payload.value"}, {"kind": "claim", "ref_id": "finance_qa_vnext_claim:85738c0c2bfff011669ca1bf1235b6a6ce0a510f077628853804a6d40067b5e6", "role": "revenue_later_value", "selector": "payload.value"}], "观察": {"value": "7.716436637390213299874529486"}} |
| 10 | update | 明确接受整个观察：finance_qa_vnext_observation:41cea51a423d05768bd28d9194464ae332b9fbfb997d47271ae275c33e9ca6ff |
| 11 | action | {"子目标": "derive_quantity", "理由": null, "操作": "growth", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:ee37030e245e747d5d885e2037453a55184850591485d626249b87058f119c00", "role": "income_earlier_value", "selector": "payload.value"}, {"kind": "claim", "ref_id": "finance_qa_vnext_claim:8349de5bff92eabfe6de9f300b7260a0c957eaef8fe46d78b188a98dd0b02d42", "role": "income_later_value", "selector": "payload.value"}], "观察": {"value": "7.547169811320754716981132075"}} |
| 12 | update | 明确接受整个观察：finance_qa_vnext_observation:6f55cc547322e2e416d25c2afe41b575e5710abb995cc3b4b497397e67b79f98 |
| 13 | action | {"子目标": "derive_quantity", "理由": null, "操作": "signed_percentage_point_gap", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:216bc01314cb5e828a3baa40839723bef28c02206f95d960ea3295e0760fd790", "role": "income_growth", "selector": "value"}, {"kind": "claim", "ref_id": "finance_qa_vnext_claim:4853da955ee6b2bc9a21c5594ea05e424e5b3db33f5c84ebbad2446f8ba53886", "role": "revenue_growth", "selector": "value"}], "观察": {"unit": "percentage_points", "value": "0.169266826069458582893397411"}} |
| 14 | update | 明确接受整个观察：finance_qa_vnext_observation:20873a1034a9fe37dfa6dc1b7983012ea7daf1254735b2ffe712a4dd21497fdb |
| 15 | action | {"子目标": "derive_quantity", "理由": null, "操作": "absolute_percentage_point_gap", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:1ac4afc202787a96b5906367fb701290881f7c99fa8468b2c45515e6934dbc28", "role": "signed_gap", "selector": "value"}], "观察": {"unit": "percentage_points", "value": "0.169266826069458582893397411"}} |
| 16 | update | 明确接受整个观察：finance_qa_vnext_observation:1d17fd16a0c5f92b03a87b4964ed5cfad0b0869e42bebfbddf5989f85829a792 |
| 17 | final | Final 校验通过：{"answer_claim_id": "finance_qa_vnext_claim:e52131f142317182acc31b2131a0421aba06300db13ab4a9a0ef7c094b713bcf", "citations": ["evidence:finqa_archive_cell:ca9ce1ceea0443d63f15b182b0dde8ed2385973453748d0790b9ec53ac84e28b", "evidence:finqa_archive_cell:cd72687d37467085a8d5a7b6c3160c12a2a1d0fba03052e6e8cd01345af7851e", "evidence:finqa_archive_cell:951cdd4db6f2d911bb8e948287ea6750ed13368842c54515dca744ee692a3b0d", "evidence:finqa_archive_cell:5933c9e29d8219df30ba9b09e78810ca2abf926cd511bc0ad6a244bf598a845d"], "kind": "final", "result": {"unit": "percentage_points", "value": "0.169266826069458582893397411"}, "state_id": "finance_qa_vnext_state:388b61257799d88c45d1e93a65d1bd18671c072015ddfa27fc198cfdfb8bd444"} |

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
    "finance_qa_vnext_claim:1ac4afc202787a96b5906367fb701290881f7c99fa8468b2c45515e6934dbc28",
    "finance_qa_vnext_claim:216bc01314cb5e828a3baa40839723bef28c02206f95d960ea3295e0760fd790",
    "finance_qa_vnext_claim:4853da955ee6b2bc9a21c5594ea05e424e5b3db33f5c84ebbad2446f8ba53886",
    "finance_qa_vnext_claim:7e70c296381e9481137d08f8793ffb16341632daca6e8f5337ecff68b37fa665",
    "finance_qa_vnext_claim:8349de5bff92eabfe6de9f300b7260a0c957eaef8fe46d78b188a98dd0b02d42",
    "finance_qa_vnext_claim:85738c0c2bfff011669ca1bf1235b6a6ce0a510f077628853804a6d40067b5e6",
    "finance_qa_vnext_claim:e52131f142317182acc31b2131a0421aba06300db13ab4a9a0ef7c094b713bcf",
    "finance_qa_vnext_claim:ee37030e245e747d5d885e2037453a55184850591485d626249b87058f119c00"
  ],
  "accepted_claims_consumed_by_operations": [
    "finance_qa_vnext_claim:1ac4afc202787a96b5906367fb701290881f7c99fa8468b2c45515e6934dbc28",
    "finance_qa_vnext_claim:216bc01314cb5e828a3baa40839723bef28c02206f95d960ea3295e0760fd790",
    "finance_qa_vnext_claim:4853da955ee6b2bc9a21c5594ea05e424e5b3db33f5c84ebbad2446f8ba53886",
    "finance_qa_vnext_claim:7e70c296381e9481137d08f8793ffb16341632daca6e8f5337ecff68b37fa665",
    "finance_qa_vnext_claim:8349de5bff92eabfe6de9f300b7260a0c957eaef8fe46d78b188a98dd0b02d42",
    "finance_qa_vnext_claim:85738c0c2bfff011669ca1bf1235b6a6ce0a510f077628853804a6d40067b5e6",
    "finance_qa_vnext_claim:ee37030e245e747d5d885e2037453a55184850591485d626249b87058f119c00"
  ],
  "accepted_but_unused_claim_ids": [],
  "not_a_complete_behavior_quotient": true
}
```
