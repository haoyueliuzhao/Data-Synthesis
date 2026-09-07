# B_H1_01

资格：qualified。接口：H1。

模型原始字段与 SYSTEM 引用展开分别保存在每轮 response.txt / language_binding.json。
下表中的 H0/H1 子目标来自已展示候选；H2 子目标和简短理由来自模型的实际提案。

| 提交 | 类型 | 实际行为／拒绝 |
| --- | --- | --- |
| 1 | action | {"子目标": "resolve_evidence", "理由": null, "操作": "lookup", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e", "role": "evidence_role_1", "selector": null}], "观察": {"payload": {"currency": "USD", "kind": "scalar_observation", "unit": "million USD", "value": "12988.7"}, "selected_ref": "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"}} |
| 2 | update | 明确接受整个观察：finance_qa_vnext_observation:0f421f3cecbe549509645ea5df27ff7ecf3dcad1517191b1f983241849e07201 |
| 3 | action | {"子目标": "resolve_evidence", "理由": null, "操作": "lookup", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43", "role": "evidence_role_2", "selector": null}], "观察": {"payload": {"currency": "USD", "kind": "scalar_observation", "unit": "million USD", "value": "13981.9"}, "selected_ref": "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43"}} |
| 4 | update | 明确接受整个观察：finance_qa_vnext_observation:aae3d6ef270d0f19bd0c002ce00b4bdddadd5962842eb0cb0fa79c51407a351f |
| 5 | action | {"子目标": "derive_quantity", "理由": null, "操作": "growth", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:148603dd33b9426c3572cf8b62e9792c6373d8e6435b0e2a39bae42a01c8c2a3", "role": "revenue_earlier_value", "selector": "payload.value"}, {"kind": "claim", "ref_id": "finance_qa_vnext_claim:307e6b1eecfab3265de0e4766a10d2bd146b47a44aa9c4f3f47e3acf7ab6f78d", "role": "revenue_later_value", "selector": "payload.value"}], "观察": {"value": "7.646646700593592892283292400"}} |
| 6 | update | 明确接受整个观察：finance_qa_vnext_observation:bc411965784f33c23c045b9424b8bff31e5a6313fce5ac26a4768a42c00ee11c |
| 7 | action | {"子目标": "resolve_evidence", "理由": null, "操作": "lookup", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2", "role": "evidence_role_3", "selector": null}], "观察": {"payload": {"currency": "USD", "kind": "scalar_observation", "unit": "million USD", "value": "742"}, "selected_ref": "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2"}} |
| 8 | update | 明确接受整个观察：finance_qa_vnext_observation:1545271b3c3b97bebbe0cf2d52d2a663e1b847421e7a152faecc423373a8f801 |
| 9 | action | {"子目标": "resolve_evidence", "理由": null, "操作": "lookup", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773", "role": "evidence_role_4", "selector": null}], "观察": {"payload": {"currency": "USD", "kind": "scalar_observation", "unit": "million USD", "value": "819.2"}, "selected_ref": "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"}} |
| 10 | update | 明确接受整个观察：finance_qa_vnext_observation:e2e06b12fc3ff37d4f2671efc3bb87c0b2bc62214c346193715b3eefd0af184c |
| 11 | action | {"子目标": "derive_quantity", "理由": null, "操作": "growth", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:012f692b9e12baa4eedf341e5ddac678ddd6fcbfc1b23ba83459bd7e2ede1d21", "role": "income_earlier_value", "selector": "payload.value"}, {"kind": "claim", "ref_id": "finance_qa_vnext_claim:895d721f8de46bc4fb05602ce6798ce770fc40f906cf198a7808da2e971a24cb", "role": "income_later_value", "selector": "payload.value"}], "观察": {"value": "10.40431266846361185983827493"}} |
| 12 | update | 明确接受整个观察：finance_qa_vnext_observation:01ec6afba23474dc3888eaf4cedfac6852e1fbb725d9e9dc654a4f23c397c66b |
| 13 | action | {"子目标": "derive_quantity", "理由": null, "操作": "signed_percentage_point_gap", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:2411ab4042b3fe37bc01afaa7f45a7a6bab1372259506cd78e41ae688bc79c2b", "role": "income_growth", "selector": "value"}, {"kind": "claim", "ref_id": "finance_qa_vnext_claim:881f81176903e9104f93101b39390c8a00a9d8b63fab123f7700cab41c8a0665", "role": "revenue_growth", "selector": "value"}], "观察": {"unit": "percentage_points", "value": "-2.757665967870018967554982530"}} |
| 14 | update | 明确接受整个观察：finance_qa_vnext_observation:ea48f7da93151bcc9e606970311c8d113b0ace402354e1b937e9aef53e504771 |
| 15 | action | {"子目标": "derive_quantity", "理由": null, "操作": "absolute_percentage_point_gap", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:dc3e0a59c4de7623fe8d1d3bfedba6a6cbf2ff155b149176898af10ae1e8209e", "role": "signed_gap", "selector": "value"}], "观察": {"unit": "percentage_points", "value": "2.757665967870018967554982530"}} |
| 16 | update | 明确接受整个观察：finance_qa_vnext_observation:1233c3d84f892a2573b19c41cfaa1e6f8afe6e57374efe27844f3cee911cb8f2 |
| 17 | final | Final 校验通过：{"answer_claim_id": "finance_qa_vnext_claim:ddf4a4190e892673d6636412db776833347673eaadd70b6dd46f8b56fad7b60f", "citations": ["evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e", "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43", "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2", "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"], "kind": "final", "result": {"unit": "percentage_points", "value": "2.757665967870018967554982530"}, "state_id": "finance_qa_vnext_state:c0f7a63a8dccd8fb4eaba7b86a2203c70d2892bfa8d9060ee21e5f2890e00103"} |

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
    "finance_qa_vnext_claim:012f692b9e12baa4eedf341e5ddac678ddd6fcbfc1b23ba83459bd7e2ede1d21",
    "finance_qa_vnext_claim:148603dd33b9426c3572cf8b62e9792c6373d8e6435b0e2a39bae42a01c8c2a3",
    "finance_qa_vnext_claim:2411ab4042b3fe37bc01afaa7f45a7a6bab1372259506cd78e41ae688bc79c2b",
    "finance_qa_vnext_claim:307e6b1eecfab3265de0e4766a10d2bd146b47a44aa9c4f3f47e3acf7ab6f78d",
    "finance_qa_vnext_claim:881f81176903e9104f93101b39390c8a00a9d8b63fab123f7700cab41c8a0665",
    "finance_qa_vnext_claim:895d721f8de46bc4fb05602ce6798ce770fc40f906cf198a7808da2e971a24cb",
    "finance_qa_vnext_claim:dc3e0a59c4de7623fe8d1d3bfedba6a6cbf2ff155b149176898af10ae1e8209e",
    "finance_qa_vnext_claim:ddf4a4190e892673d6636412db776833347673eaadd70b6dd46f8b56fad7b60f"
  ],
  "accepted_claims_consumed_by_operations": [
    "finance_qa_vnext_claim:012f692b9e12baa4eedf341e5ddac678ddd6fcbfc1b23ba83459bd7e2ede1d21",
    "finance_qa_vnext_claim:148603dd33b9426c3572cf8b62e9792c6373d8e6435b0e2a39bae42a01c8c2a3",
    "finance_qa_vnext_claim:2411ab4042b3fe37bc01afaa7f45a7a6bab1372259506cd78e41ae688bc79c2b",
    "finance_qa_vnext_claim:307e6b1eecfab3265de0e4766a10d2bd146b47a44aa9c4f3f47e3acf7ab6f78d",
    "finance_qa_vnext_claim:881f81176903e9104f93101b39390c8a00a9d8b63fab123f7700cab41c8a0665",
    "finance_qa_vnext_claim:895d721f8de46bc4fb05602ce6798ce770fc40f906cf198a7808da2e971a24cb",
    "finance_qa_vnext_claim:dc3e0a59c4de7623fe8d1d3bfedba6a6cbf2ff155b149176898af10ae1e8209e"
  ],
  "accepted_but_unused_claim_ids": [],
  "not_a_complete_behavior_quotient": true
}
```
