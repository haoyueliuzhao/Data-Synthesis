# B_H2_01

资格：qualified。接口：H2。

模型原始字段与 SYSTEM 引用展开分别保存在每轮 response.txt / language_binding.json。
下表中的 H0/H1 子目标来自已展示候选；H2 子目标和简短理由来自模型的实际提案。

| 提交 | 类型 | 实际行为／拒绝 |
| --- | --- | --- |
| 1 | action | {"子目标": "Calculate revenue growth from FY2015 to FY2016.", "理由": "Use growth operation with earlier=E1 (FY2015 revenue) and later=E2 (FY2016 revenue) to get revenue growth percentage.", "操作": "growth", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e", "role": "earlier"}, {"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43", "role": "later"}], "观察": {"value": "7.646646700593592892283292400"}} |
| 2 | update | 明确接受整个观察：finance_qa_vnext_observation:97c36320d2e91186d133e8b046566cd5f1b3e6aac95ad55d303d61650be43bc2 |
| 3 | action | {"子目标": "Calculate operating-income growth from FY2015 to FY2016.", "理由": "Use the growth operation on operating income evidence E3 (FY2015) and E4 (FY2016) to get the second growth rate needed for the spread.", "操作": "growth", "输入": [{"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2", "role": "earlier"}, {"kind": "evidence", "ref_id": "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773", "role": "later"}], "观察": {"value": "10.40431266846361185983827493"}} |
| 4 | update | 明确接受整个观察：finance_qa_vnext_observation:081c08bfd0bcc471ec0f6480cd7f53996610fa880cb29a1053d30196bed95308 |
| 5 | action | 拒绝：semantic.arity |
| 6 | action | {"子目标": "Compute the signed percentage-point gap between revenue growth and operating-income growth.", "理由": "Use signed_percentage_point_gap with reference_percent=C1 (revenue growth) and observed_percent=C2 (operating-income growth) to get observed - reference.", "操作": "signed_percentage_point_gap", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:ce3548222604d7da2ff128722f3450555b0f09f842a7687bce14c995e74e8697", "role": "reference_percent"}, {"kind": "claim", "ref_id": "finance_qa_vnext_claim:3f852cf9e3de7cc747f74620ee31f6071f5859baa2832fb0e401d5874c79c60c", "role": "observed_percent"}], "观察": {"unit": "percentage_points", "value": "2.757665967870018967554982530"}} |
| 7 | update | 明确接受整个观察：finance_qa_vnext_observation:5fdb459b140e3045e89674308a22d4159c966aa60cf4d93bc2ab9154177dab61 |
| 8 | action | {"子目标": "Compute the absolute percentage-point spread between revenue growth and operating-income growth.", "理由": "C3 holds the signed gap. Apply absolute_percentage_point_gap to C3 to get the absolute spread.", "操作": "absolute_percentage_point_gap", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:54975919b928b5135c2395232405f0275e002e57edb92412eb9f099f9e91b4ea", "role": "signed_gap"}], "观察": {"unit": "percentage_points", "value": "2.757665967870018967554982530"}} |
| 9 | update | 明确接受整个观察：finance_qa_vnext_observation:adfd5914d4a122facd49f169c752af7ab673d2b1012faa8850732dd4bd88e89f |
| 10 | final | Final 校验通过：{"answer_claim_id": "finance_qa_vnext_claim:0579989108c0a16caea4a031e7504e2672e5992e0c805c297f0ed0908e527d8a", "citations": ["evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e", "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43", "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2", "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"], "kind": "final", "result": {"unit": "percentage_points", "value": "2.757665967870018967554982530"}, "state_id": "finance_qa_vnext_state:76c206d44f8dbd4ec2bb0a673984de68fba3e42541867f24fe7a6703775b0c3e"} |

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
                "evidence": "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"
              },
              {
                "evidence": "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43"
              }
            ],
            "parameters": {}
          },
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
          }
        ],
        "parameters": {}
      }
    ],
    "parameters": {}
  },
  "signature": "finite_method:55aeec0705078d57550735c41d57956e764b287a88e9897be16c6e30f32211db",
  "answer_lineage": [
    "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
    "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
    "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
    "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
  ],
  "used_accepted_claim_ids": [
    "finance_qa_vnext_claim:0579989108c0a16caea4a031e7504e2672e5992e0c805c297f0ed0908e527d8a",
    "finance_qa_vnext_claim:3f852cf9e3de7cc747f74620ee31f6071f5859baa2832fb0e401d5874c79c60c",
    "finance_qa_vnext_claim:54975919b928b5135c2395232405f0275e002e57edb92412eb9f099f9e91b4ea",
    "finance_qa_vnext_claim:ce3548222604d7da2ff128722f3450555b0f09f842a7687bce14c995e74e8697"
  ],
  "accepted_claims_consumed_by_operations": [
    "finance_qa_vnext_claim:3f852cf9e3de7cc747f74620ee31f6071f5859baa2832fb0e401d5874c79c60c",
    "finance_qa_vnext_claim:54975919b928b5135c2395232405f0275e002e57edb92412eb9f099f9e91b4ea",
    "finance_qa_vnext_claim:ce3548222604d7da2ff128722f3450555b0f09f842a7687bce14c995e74e8697"
  ],
  "accepted_but_unused_claim_ids": [],
  "not_a_complete_behavior_quotient": true
}
```
