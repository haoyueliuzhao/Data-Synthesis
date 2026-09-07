# B_H0_01

资格：qualified。接口：H0。

模型原始字段与 SYSTEM 引用展开分别保存在每轮 response.txt / language_binding.json。
下表中的 H0/H1 子目标来自已展示候选；H2 子目标和简短理由来自模型的实际提案。

| 提交 | 类型 | 实际行为／拒绝 |
| --- | --- | --- |
| 1 | action | {"子目标": "resolve_evidence", "理由": null, "操作": "lookup", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e", "role": "evidence_role_1", "selector": null}], "观察": {"payload": {"currency": "USD", "kind": "scalar_observation", "unit": "million USD", "value": "12988.7"}, "selected_ref": "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"}} |
| 2 | update | 明确接受整个观察：finance_qa_vnext_observation:618e6bd8d29516b47688cde89e5d2e54232b4834eb4e915a7036609d2c5281cb |
| 3 | action | {"子目标": "resolve_evidence", "理由": null, "操作": "lookup", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43", "role": "evidence_role_2", "selector": null}], "观察": {"payload": {"currency": "USD", "kind": "scalar_observation", "unit": "million USD", "value": "13981.9"}, "selected_ref": "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43"}} |
| 4 | update | 明确接受整个观察：finance_qa_vnext_observation:1bcf929e74d8177fd48e8f2fcb8aa1490b22db774ae6428cb4df6bced30e1b7c |
| 5 | action | {"子目标": "resolve_evidence", "理由": null, "操作": "lookup", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2", "role": "evidence_role_3", "selector": null}], "观察": {"payload": {"currency": "USD", "kind": "scalar_observation", "unit": "million USD", "value": "742"}, "selected_ref": "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2"}} |
| 6 | update | 明确接受整个观察：finance_qa_vnext_observation:ec86cb7c047ec25b3e4e6705e40a9f16b7924b753de0d81585422a98302d0848 |
| 7 | action | {"子目标": "derive_quantity", "理由": null, "操作": "growth", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:4445423d3d296029b7a0886d690aada0c6470ec73af9cdd247e2c71c7073c6c8", "role": "revenue_earlier_value", "selector": "payload.value"}, {"kind": "claim", "ref_id": "finance_qa_vnext_claim:faef981b5aa5d3827eadf7dec7a1fbeb43f2110975d91e6842eac49377a8a32c", "role": "revenue_later_value", "selector": "payload.value"}], "观察": {"value": "7.646646700593592892283292400"}} |
| 8 | update | 明确接受整个观察：finance_qa_vnext_observation:814ed477064b2b924974a16779d4bb12a77faa12f56891edf8b9ef850d0af57c |
| 9 | action | {"子目标": "resolve_evidence", "理由": null, "操作": "lookup", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773", "role": "evidence_role_4", "selector": null}], "观察": {"payload": {"currency": "USD", "kind": "scalar_observation", "unit": "million USD", "value": "819.2"}, "selected_ref": "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"}} |
| 10 | update | 明确接受整个观察：finance_qa_vnext_observation:5b538bb3ae3fd231fc9c1863f4e97870454ee14a5c046e45ecf48f1214907072 |
| 11 | action | {"子目标": "derive_quantity", "理由": null, "操作": "growth", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:cccca07d69d06cf0572fc25a73bd27d3be6fc93a583ae1187115dd191e47952d", "role": "income_earlier_value", "selector": "payload.value"}, {"kind": "claim", "ref_id": "finance_qa_vnext_claim:21997bfe564aef0a70de15cd3afe8b5933fb1e5746f655fc0a01600327391e21", "role": "income_later_value", "selector": "payload.value"}], "观察": {"value": "10.40431266846361185983827493"}} |
| 12 | update | 明确接受整个观察：finance_qa_vnext_observation:c59587bd3d87167149610a84262ffe6f4fc2b3d248fda6c0197d5b6400224cf4 |
| 13 | action | {"子目标": "derive_quantity", "理由": null, "操作": "signed_percentage_point_gap", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:1f87dc29fccebfa5f6fe420dc96cd4f040b5323d8f54467cd81aac06f7fad65e", "role": "income_growth", "selector": "value"}, {"kind": "claim", "ref_id": "finance_qa_vnext_claim:90eb81baa2e9b4cc37577abf2e504f75fce80bfdf37fbcce59f44e756274e05e", "role": "revenue_growth", "selector": "value"}], "观察": {"unit": "percentage_points", "value": "-2.757665967870018967554982530"}} |
| 14 | update | 明确接受整个观察：finance_qa_vnext_observation:11a455e0ba2334ff04252693f0c6e8965393de4f371bc584e609c4526f90fe55 |
| 15 | action | {"子目标": "derive_quantity", "理由": null, "操作": "absolute_percentage_point_gap", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:ae2dea5722f1e162751bf8553cf598f3974dffa35c96676c9a185bacadbec8e9", "role": "signed_gap", "selector": "value"}], "观察": {"unit": "percentage_points", "value": "2.757665967870018967554982530"}} |
| 16 | update | 明确接受整个观察：finance_qa_vnext_observation:b1c26ede01fa4ad4afbec7a187aa9653df054a35874ca811d0ef7d0936744bd8 |
| 17 | final | Final 校验通过：{"answer_claim_id": "finance_qa_vnext_claim:74fbf539c9db51ead1166734b7e305573efaaa960980a11fb32f4cef9a417727", "citations": ["evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43", "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2", "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e", "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"], "kind": "final", "result": {"unit": "percentage_points", "value": "2.757665967870018967554982530"}, "state_id": "finance_qa_vnext_state:fde7f07afd0c6cd903aac2671d579a801d7577bef1699e0b65b6740d74f5455b"} |

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
                "evidence": "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2"
              },
              {
                "evidence": "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
              }
            ],
            "parameters": {}
          },
          {
            "operation": "growth",
            "inputs": [
              {
                "evidence": "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"
              },
              {
                "evidence": "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43"
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
  "signature": "finite_method:e3037aefea1e585c28fc8d6e0d50b86af46e2d867ae36ab108af22449c15f272",
  "answer_lineage": [
    "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
    "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
    "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
    "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
  ],
  "used_accepted_claim_ids": [
    "finance_qa_vnext_claim:1f87dc29fccebfa5f6fe420dc96cd4f040b5323d8f54467cd81aac06f7fad65e",
    "finance_qa_vnext_claim:21997bfe564aef0a70de15cd3afe8b5933fb1e5746f655fc0a01600327391e21",
    "finance_qa_vnext_claim:4445423d3d296029b7a0886d690aada0c6470ec73af9cdd247e2c71c7073c6c8",
    "finance_qa_vnext_claim:74fbf539c9db51ead1166734b7e305573efaaa960980a11fb32f4cef9a417727",
    "finance_qa_vnext_claim:90eb81baa2e9b4cc37577abf2e504f75fce80bfdf37fbcce59f44e756274e05e",
    "finance_qa_vnext_claim:ae2dea5722f1e162751bf8553cf598f3974dffa35c96676c9a185bacadbec8e9",
    "finance_qa_vnext_claim:cccca07d69d06cf0572fc25a73bd27d3be6fc93a583ae1187115dd191e47952d",
    "finance_qa_vnext_claim:faef981b5aa5d3827eadf7dec7a1fbeb43f2110975d91e6842eac49377a8a32c"
  ],
  "accepted_claims_consumed_by_operations": [
    "finance_qa_vnext_claim:1f87dc29fccebfa5f6fe420dc96cd4f040b5323d8f54467cd81aac06f7fad65e",
    "finance_qa_vnext_claim:21997bfe564aef0a70de15cd3afe8b5933fb1e5746f655fc0a01600327391e21",
    "finance_qa_vnext_claim:4445423d3d296029b7a0886d690aada0c6470ec73af9cdd247e2c71c7073c6c8",
    "finance_qa_vnext_claim:90eb81baa2e9b4cc37577abf2e504f75fce80bfdf37fbcce59f44e756274e05e",
    "finance_qa_vnext_claim:ae2dea5722f1e162751bf8553cf598f3974dffa35c96676c9a185bacadbec8e9",
    "finance_qa_vnext_claim:cccca07d69d06cf0572fc25a73bd27d3be6fc93a583ae1187115dd191e47952d",
    "finance_qa_vnext_claim:faef981b5aa5d3827eadf7dec7a1fbeb43f2110975d91e6842eac49377a8a32c"
  ],
  "accepted_but_unused_claim_ids": [],
  "not_a_complete_behavior_quotient": true
}
```
