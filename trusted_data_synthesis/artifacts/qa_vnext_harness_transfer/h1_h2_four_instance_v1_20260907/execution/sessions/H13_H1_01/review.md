# H13_H1_01

资格：qualified。接口：H1。

模型原始字段与 SYSTEM 引用展开分别保存在每轮 response.txt / language_binding.json。
下表中的 H0/H1 子目标来自已展示候选；H2 子目标和简短理由来自模型的实际提案。

| 提交 | 类型 | 实际行为／拒绝 |
| --- | --- | --- |
| 1 | action | {"子目标": "resolve_evidence", "理由": null, "操作": "lookup", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:ca9ce1ceea0443d63f15b182b0dde8ed2385973453748d0790b9ec53ac84e28b", "role": "evidence_role_1", "selector": null}], "观察": {"payload": {"currency": "USD", "kind": "scalar_observation", "unit": "million USD", "value": "1594"}, "selected_ref": "evidence:finqa_archive_cell:ca9ce1ceea0443d63f15b182b0dde8ed2385973453748d0790b9ec53ac84e28b"}} |
| 2 | update | 明确接受整个观察：finance_qa_vnext_observation:c9bbfad1d23cf44eb9eebdf6b037c0a7b898c7018cf0de39742d7872f419451b |
| 3 | action | {"子目标": "resolve_evidence", "理由": null, "操作": "lookup", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:cd72687d37467085a8d5a7b6c3160c12a2a1d0fba03052e6e8cd01345af7851e", "role": "evidence_role_2", "selector": null}], "观察": {"payload": {"currency": "USD", "kind": "scalar_observation", "unit": "million USD", "value": "1717"}, "selected_ref": "evidence:finqa_archive_cell:cd72687d37467085a8d5a7b6c3160c12a2a1d0fba03052e6e8cd01345af7851e"}} |
| 4 | update | 明确接受整个观察：finance_qa_vnext_observation:bfb4d4cc21a49ce28870154fd906cc553cefc2cadaa8410a0514038d6244106e |
| 5 | action | {"子目标": "resolve_evidence", "理由": null, "操作": "lookup", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:951cdd4db6f2d911bb8e948287ea6750ed13368842c54515dca744ee692a3b0d", "role": "evidence_role_3", "selector": null}], "观察": {"payload": {"currency": "USD", "kind": "scalar_observation", "unit": "million USD", "value": "159"}, "selected_ref": "evidence:finqa_archive_cell:951cdd4db6f2d911bb8e948287ea6750ed13368842c54515dca744ee692a3b0d"}} |
| 6 | update | 明确接受整个观察：finance_qa_vnext_observation:cceab54e9b0ef90c3ade1aea98be0feb3e55a33c33a724ef443cd3f43efc0e7a |
| 7 | action | {"子目标": "resolve_evidence", "理由": null, "操作": "lookup", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:5933c9e29d8219df30ba9b09e78810ca2abf926cd511bc0ad6a244bf598a845d", "role": "evidence_role_4", "selector": null}], "观察": {"payload": {"currency": "USD", "kind": "scalar_observation", "unit": "million USD", "value": "171"}, "selected_ref": "evidence:finqa_archive_cell:5933c9e29d8219df30ba9b09e78810ca2abf926cd511bc0ad6a244bf598a845d"}} |
| 8 | update | 明确接受整个观察：finance_qa_vnext_observation:2fe40d59fc0cecb3efa1e710a49d38c1f7182805af554e00d2909258e22e4d91 |
| 9 | action | {"子目标": "derive_quantity", "理由": null, "操作": "growth", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:6f88bc3566038685cb4e9591da9517b9fa90084bf47fc59b213baf4b8badcb03", "role": "revenue_earlier_value", "selector": "payload.value"}, {"kind": "claim", "ref_id": "finance_qa_vnext_claim:1febe301262be0dff167f7f2224f6849baee5c7af8f8e7cbe39d20cd02cb714b", "role": "revenue_later_value", "selector": "payload.value"}], "观察": {"value": "7.716436637390213299874529486"}} |
| 10 | update | 明确接受整个观察：finance_qa_vnext_observation:f8b07c9284426965c8f0e92f989c51fc6477fc4bee215df1df304943d72f19ff |
| 11 | action | {"子目标": "derive_quantity", "理由": null, "操作": "growth", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:2cb7db3f055dae84257a24cb74a3ebad0887dd910dd3fa0b659a6b41e1bf11cb", "role": "income_earlier_value", "selector": "payload.value"}, {"kind": "claim", "ref_id": "finance_qa_vnext_claim:2514d28f1b7e9de4e40f8f9db8e7d4d0b0fd4e5ae3618a8a14c2632b3c2fba1e", "role": "income_later_value", "selector": "payload.value"}], "观察": {"value": "7.547169811320754716981132075"}} |
| 12 | update | 明确接受整个观察：finance_qa_vnext_observation:7ff1b7b1d5693177699073c5219091018d9309323aba0dfbd71eb511370f36f8 |
| 13 | action | {"子目标": "derive_quantity", "理由": null, "操作": "signed_percentage_point_gap", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:ebabee7ca8deaef290517fef83542035831744b35051f5ab1fabdb95aabe44e8", "role": "income_growth", "selector": "value"}, {"kind": "claim", "ref_id": "finance_qa_vnext_claim:ef54379afc73674d990470b10de18a54306d58ee9647413c9228e62dd6c07201", "role": "revenue_growth", "selector": "value"}], "观察": {"unit": "percentage_points", "value": "0.169266826069458582893397411"}} |
| 14 | update | 明确接受整个观察：finance_qa_vnext_observation:1829c3fc22e87e9092b118a0b5c5d47171358f12862224b42ef1ac63c15e52f4 |
| 15 | action | {"子目标": "derive_quantity", "理由": null, "操作": "absolute_percentage_point_gap", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:58885a082986e72b8a95340c5c1cae3542f8405ba2ab7b28a2a97aa117443f65", "role": "signed_gap", "selector": "value"}], "观察": {"unit": "percentage_points", "value": "0.169266826069458582893397411"}} |
| 16 | update | 明确接受整个观察：finance_qa_vnext_observation:a80df4d0c651855804485c4955b67a9bfe884bf5bb7c03b87beb245bef86abce |
| 17 | final | Final 校验通过：{"answer_claim_id": "finance_qa_vnext_claim:5515078685567d181aa743c372bf4322fafbd2b522af76c7d5c76a6f8d48767d", "citations": ["evidence:finqa_archive_cell:ca9ce1ceea0443d63f15b182b0dde8ed2385973453748d0790b9ec53ac84e28b", "evidence:finqa_archive_cell:cd72687d37467085a8d5a7b6c3160c12a2a1d0fba03052e6e8cd01345af7851e", "evidence:finqa_archive_cell:951cdd4db6f2d911bb8e948287ea6750ed13368842c54515dca744ee692a3b0d", "evidence:finqa_archive_cell:5933c9e29d8219df30ba9b09e78810ca2abf926cd511bc0ad6a244bf598a845d"], "kind": "final", "result": {"unit": "percentage_points", "value": "0.169266826069458582893397411"}, "state_id": "finance_qa_vnext_state:e1a32ebc918a7e475c5175c3fe501ad55f233f423a97a217aa556de07d6c4c42"} |

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
    "finance_qa_vnext_claim:1febe301262be0dff167f7f2224f6849baee5c7af8f8e7cbe39d20cd02cb714b",
    "finance_qa_vnext_claim:2514d28f1b7e9de4e40f8f9db8e7d4d0b0fd4e5ae3618a8a14c2632b3c2fba1e",
    "finance_qa_vnext_claim:2cb7db3f055dae84257a24cb74a3ebad0887dd910dd3fa0b659a6b41e1bf11cb",
    "finance_qa_vnext_claim:5515078685567d181aa743c372bf4322fafbd2b522af76c7d5c76a6f8d48767d",
    "finance_qa_vnext_claim:58885a082986e72b8a95340c5c1cae3542f8405ba2ab7b28a2a97aa117443f65",
    "finance_qa_vnext_claim:6f88bc3566038685cb4e9591da9517b9fa90084bf47fc59b213baf4b8badcb03",
    "finance_qa_vnext_claim:ebabee7ca8deaef290517fef83542035831744b35051f5ab1fabdb95aabe44e8",
    "finance_qa_vnext_claim:ef54379afc73674d990470b10de18a54306d58ee9647413c9228e62dd6c07201"
  ],
  "accepted_claims_consumed_by_operations": [
    "finance_qa_vnext_claim:1febe301262be0dff167f7f2224f6849baee5c7af8f8e7cbe39d20cd02cb714b",
    "finance_qa_vnext_claim:2514d28f1b7e9de4e40f8f9db8e7d4d0b0fd4e5ae3618a8a14c2632b3c2fba1e",
    "finance_qa_vnext_claim:2cb7db3f055dae84257a24cb74a3ebad0887dd910dd3fa0b659a6b41e1bf11cb",
    "finance_qa_vnext_claim:58885a082986e72b8a95340c5c1cae3542f8405ba2ab7b28a2a97aa117443f65",
    "finance_qa_vnext_claim:6f88bc3566038685cb4e9591da9517b9fa90084bf47fc59b213baf4b8badcb03",
    "finance_qa_vnext_claim:ebabee7ca8deaef290517fef83542035831744b35051f5ab1fabdb95aabe44e8",
    "finance_qa_vnext_claim:ef54379afc73674d990470b10de18a54306d58ee9647413c9228e62dd6c07201"
  ],
  "accepted_but_unused_claim_ids": [],
  "not_a_complete_behavior_quotient": true
}
```
