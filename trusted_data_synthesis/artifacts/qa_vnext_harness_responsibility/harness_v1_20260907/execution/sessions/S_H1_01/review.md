# S_H1_01

资格：qualified。接口：H1。

模型原始字段与 SYSTEM 引用展开分别保存在每轮 response.txt / language_binding.json。
下表中的 H0/H1 子目标来自已展示候选；H2 子目标和简短理由来自模型的实际提案。

| 提交 | 类型 | 实际行为／拒绝 |
| --- | --- | --- |
| 1 | action | {"子目标": "select_total_support", "理由": null, "操作": "share_ratio", "输入": [{"kind": "evidence", "ref_id": "part_whole_share_numeric_evidence:f8ad13511fa22b6d64183fb4b5f5cd114faaf185520d57b0d1f4c7571573ad7a", "role": "numerator"}, {"kind": "evidence", "ref_id": "part_whole_share_numeric_evidence:033a430a60a5d3243f701d231a10b71564b48b2abeae58d635c42a2811e7638f", "role": "denominator"}], "观察": {"currency": "dollar_as_disclosed", "definition": "freight divided by legitimate operating revenue total", "lineage": ["part_whole_share_numeric_evidence:033a430a60a5d3243f701d231a10b71564b48b2abeae58d635c42a2811e7638f", "part_whole_share_numeric_evidence:f8ad13511fa22b6d64183fb4b5f5cd114faaf185520d57b0d1f4c7571573ad7a"], "metric": "freight_share_ratio", "period": "2015", "scope": "consolidated_issuer", "subject": "Union Pacific Corporation and subsidiaries", "unit": "ratio", "value": "0.93508458258836473662494842525099711181405583826159"}} |
| 2 | update | 明确接受整个观察：finance_qa_vnext_observation:dabe6b14f40498a089d2a906089734b0c8b722299da01230460860b98a4d8427 |
| 3 | action | {"子目标": "derive_quantity", "理由": null, "操作": "scale_percent", "输入": [{"kind": "claim", "ref_id": "finance_qa_vnext_claim:d00922f5d38d0e10267d2bfb5c065963c88e9b9cb5c89b4b0aa1169cac33c480", "role": "ratio"}], "观察": {"currency": "dollar_as_disclosed", "definition": "freight share in percent", "lineage": ["part_whole_share_numeric_evidence:033a430a60a5d3243f701d231a10b71564b48b2abeae58d635c42a2811e7638f", "part_whole_share_numeric_evidence:f8ad13511fa22b6d64183fb4b5f5cd114faaf185520d57b0d1f4c7571573ad7a"], "metric": "freight_share_percent", "period": "2015", "scope": "consolidated_issuer", "subject": "Union Pacific Corporation and subsidiaries", "unit": "percent", "value": "93.508458258836473662494842525099711181405583826159"}} |
| 4 | update | 明确接受整个观察：finance_qa_vnext_observation:97957f6ca863173dfb369689e4f6ad885baf416cb9e67dc1771f5d27ddd85903 |
| 5 | final | Final 校验通过：{"answer_claim_id": "finance_qa_vnext_claim:858e9e2834bd9a99f8806024ed877e5a579b9e1c3e4bbb9d6821f1c950427a5a", "citations": ["part_whole_share_numeric_evidence:033a430a60a5d3243f701d231a10b71564b48b2abeae58d635c42a2811e7638f", "part_whole_share_numeric_evidence:f8ad13511fa22b6d64183fb4b5f5cd114faaf185520d57b0d1f4c7571573ad7a"], "kind": "final", "result": {"unit": "percent", "value": "93.508458"}, "state_id": "finance_qa_vnext_state:dbe26ddab36a4cae510089014646d44cbfdd69174ceabb0b08d7a24f2d2e10fb"} |

## 实际 Final 支持图（不是完整行为商）

```json
{
  "tree": {
    "operation": "scale_percent",
    "inputs": [
      {
        "operation": "share_ratio",
        "inputs": [
          {
            "evidence": "part_whole_share_numeric_evidence:f8ad13511fa22b6d64183fb4b5f5cd114faaf185520d57b0d1f4c7571573ad7a"
          },
          {
            "evidence": "part_whole_share_numeric_evidence:033a430a60a5d3243f701d231a10b71564b48b2abeae58d635c42a2811e7638f"
          }
        ],
        "parameters": {}
      }
    ],
    "parameters": {}
  },
  "signature": "finite_method:46366a0424e9b96595ab1697dc5427bf6cfd0e735a2c9ecc75999d2ada094166",
  "answer_lineage": [
    "part_whole_share_numeric_evidence:033a430a60a5d3243f701d231a10b71564b48b2abeae58d635c42a2811e7638f",
    "part_whole_share_numeric_evidence:f8ad13511fa22b6d64183fb4b5f5cd114faaf185520d57b0d1f4c7571573ad7a"
  ],
  "used_accepted_claim_ids": [
    "finance_qa_vnext_claim:858e9e2834bd9a99f8806024ed877e5a579b9e1c3e4bbb9d6821f1c950427a5a",
    "finance_qa_vnext_claim:d00922f5d38d0e10267d2bfb5c065963c88e9b9cb5c89b4b0aa1169cac33c480"
  ],
  "accepted_claims_consumed_by_operations": [
    "finance_qa_vnext_claim:d00922f5d38d0e10267d2bfb5c065963c88e9b9cb5c89b4b0aa1169cac33c480"
  ],
  "accepted_but_unused_claim_ids": [],
  "not_a_complete_behavior_quotient": true
}
```
