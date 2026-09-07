# B_H0_02

资格：qualified。接口：H0。

模型原始字段与 SYSTEM 引用展开分别保存在每轮 response.txt / language_binding.json。
下表中的 H0/H1 子目标来自已展示候选；H2 子目标和简短理由来自模型的实际提案。

| 提交 | 类型 | 实际行为／拒绝 |
| --- | --- | --- |
| 1 | action | {"子目标": "resolve_evidence", "理由": null, "操作": "lookup", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e", "role": "evidence_role_1", "selector": null}], "观察": {"payload": {"currency": "USD", "kind": "scalar_observation", "unit": "million USD", "value": "12988.7"}, "selected_ref": "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"}} |
| 2 | update | 明确接受整个观察：finance_qa_vnext_observation:d31bd11abf0dd1c0fd2e9dc92228abdcb6be2b59f0cbf8bf81a2eebed65810e3 |
| 3 | action | {"子目标": "resolve_evidence", "理由": null, "操作": "lookup", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43", "role": "evidence_role_2", "selector": null}], "观察": {"payload": {"currency": "USD", "kind": "scalar_observation", "unit": "million USD", "value": "13981.9"}, "selected_ref": "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43"}} |
| 4 | update | 明确接受整个观察：finance_qa_vnext_observation:86b9180c0f9f218504dc1100ea29d2bd1c718f63253155b1d429d864fb6f9fbd |
| 5 | action | {"子目标": "derive_quantity", "理由": null, "操作": "growth", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:bea3ce088889beece58572af1ddcd5c75959730d2ed04b016568e7582e341a37", "role": "revenue_earlier_value", "selector": "payload.value"}, {"kind": "claim", "ref_id": "finance_qa_vnext_claim:53d5b4c39ec398b58acf4e607afbb071c5ad05ae4c5f89c442f6e8aed2a1253d", "role": "revenue_later_value", "selector": "payload.value"}], "观察": {"value": "7.646646700593592892283292400"}} |
| 6 | update | 明确接受整个观察：finance_qa_vnext_observation:4e5a0b39c784f5795eae585b66ce11958e73d9883ec6fd9fd5931f0d27e63603 |
| 7 | action | {"子目标": "resolve_evidence", "理由": null, "操作": "lookup", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2", "role": "evidence_role_3", "selector": null}], "观察": {"payload": {"currency": "USD", "kind": "scalar_observation", "unit": "million USD", "value": "742"}, "selected_ref": "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2"}} |
| 8 | update | 明确接受整个观察：finance_qa_vnext_observation:829ab71aad12851ef1c593f4c80f386c855f176eb996eebb0762bb16401f6df3 |
| 9 | action | {"子目标": "resolve_evidence", "理由": null, "操作": "lookup", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773", "role": "evidence_role_4", "selector": null}], "观察": {"payload": {"currency": "USD", "kind": "scalar_observation", "unit": "million USD", "value": "819.2"}, "selected_ref": "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"}} |
| 10 | update | 明确接受整个观察：finance_qa_vnext_observation:68d6721f4df8e7d0ff044698951dec3fda1cad45012391b7fa83a0892a7ba044 |
| 11 | action | {"子目标": "derive_quantity", "理由": null, "操作": "growth", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:674b69880267db83d949cd35bbff16e74d409bc697f301c1811ecff7309e6365", "role": "income_earlier_value", "selector": "payload.value"}, {"kind": "claim", "ref_id": "finance_qa_vnext_claim:c13631be9006a270f2111c5dc04331fda9d08fcf037be5de8f1323b640ccef4b", "role": "income_later_value", "selector": "payload.value"}], "观察": {"value": "10.40431266846361185983827493"}} |
| 12 | update | 明确接受整个观察：finance_qa_vnext_observation:f569a171b8f67473deacb3aef3502b4d95e1f73cfd25681258f4dbcb59450cfc |
| 13 | action | {"子目标": "derive_quantity", "理由": null, "操作": "signed_percentage_point_gap", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:f311bd36443c0cd3af3799d830bcf9a8a05b78da154e7793171d8a825a929274", "role": "income_growth", "selector": "value"}, {"kind": "claim", "ref_id": "finance_qa_vnext_claim:b53d65970f36dbb817bf57821c384e352aff63bce10ed7641b9426e53971ee04", "role": "revenue_growth", "selector": "value"}], "观察": {"unit": "percentage_points", "value": "-2.757665967870018967554982530"}} |
| 14 | update | 明确接受整个观察：finance_qa_vnext_observation:863ff37b50c35627b9e43836d8aadbe54b6c1a20111e964e793c056f1cd4c983 |
| 15 | action | {"子目标": "derive_quantity", "理由": null, "操作": "absolute_percentage_point_gap", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:976067e1240eb656302d7d990bb3572acb37fb67d5068350d3f1e889d239aecd", "role": "signed_gap", "selector": "value"}], "观察": {"unit": "percentage_points", "value": "2.757665967870018967554982530"}} |
| 16 | update | 明确接受整个观察：finance_qa_vnext_observation:93bb935eb4b4d8efb21c1b47c030a557cc7360cafd1be43452eb3c9a97950ccc |
| 17 | final | Final 校验通过：{"answer_claim_id": "finance_qa_vnext_claim:7dd79d8e87d99ed7551be5b72f7dabff7da3c08d9339c8cec13d3141188152ce", "citations": ["evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e", "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43", "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2", "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"], "kind": "final", "result": {"unit": "percentage_points", "value": "2.757665967870018967554982530"}, "state_id": "finance_qa_vnext_state:3096010e3db7b357dd40f457eae4a0d928d2f27003fe8a5c2629a22a46e726cb"} |

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
    "finance_qa_vnext_claim:53d5b4c39ec398b58acf4e607afbb071c5ad05ae4c5f89c442f6e8aed2a1253d",
    "finance_qa_vnext_claim:674b69880267db83d949cd35bbff16e74d409bc697f301c1811ecff7309e6365",
    "finance_qa_vnext_claim:7dd79d8e87d99ed7551be5b72f7dabff7da3c08d9339c8cec13d3141188152ce",
    "finance_qa_vnext_claim:976067e1240eb656302d7d990bb3572acb37fb67d5068350d3f1e889d239aecd",
    "finance_qa_vnext_claim:b53d65970f36dbb817bf57821c384e352aff63bce10ed7641b9426e53971ee04",
    "finance_qa_vnext_claim:bea3ce088889beece58572af1ddcd5c75959730d2ed04b016568e7582e341a37",
    "finance_qa_vnext_claim:c13631be9006a270f2111c5dc04331fda9d08fcf037be5de8f1323b640ccef4b",
    "finance_qa_vnext_claim:f311bd36443c0cd3af3799d830bcf9a8a05b78da154e7793171d8a825a929274"
  ],
  "accepted_claims_consumed_by_operations": [
    "finance_qa_vnext_claim:53d5b4c39ec398b58acf4e607afbb071c5ad05ae4c5f89c442f6e8aed2a1253d",
    "finance_qa_vnext_claim:674b69880267db83d949cd35bbff16e74d409bc697f301c1811ecff7309e6365",
    "finance_qa_vnext_claim:976067e1240eb656302d7d990bb3572acb37fb67d5068350d3f1e889d239aecd",
    "finance_qa_vnext_claim:b53d65970f36dbb817bf57821c384e352aff63bce10ed7641b9426e53971ee04",
    "finance_qa_vnext_claim:bea3ce088889beece58572af1ddcd5c75959730d2ed04b016568e7582e341a37",
    "finance_qa_vnext_claim:c13631be9006a270f2111c5dc04331fda9d08fcf037be5de8f1323b640ccef4b",
    "finance_qa_vnext_claim:f311bd36443c0cd3af3799d830bcf9a8a05b78da154e7793171d8a825a929274"
  ],
  "accepted_but_unused_claim_ids": [],
  "not_a_complete_behavior_quotient": true
}
```
