# task_panel_B01：合格 QA 轨迹

[返回审阅索引](README.md)

## 任务与结果

Across FY2015 to FY2016, what is the absolute percentage-point spread between CDW Corporation's revenue growth and operating-income growth after calculating both growth rates?

实验：`task_panel`；会话：`B01`；提示分层：`统一面板条件`。

冻结资格：success；完整提交18次，其中准入17次、未准入1次。

最终答案（原始result字段，保持数值精度和单位）：


```json
{
  "unit": "percentage_points",
  "value": "2.757665967870018967554982530"
}
```


<details>
<summary>展开最终答案、引用及既有验证结果</summary>

```json
{
  "answer": {
    "answer_claim_id": "finance_qa_vnext_claim:ba15bf9e93a7cf6fe796d10f82f6e4e2c7ee0dca63201b93f243e57e870d2c14",
    "citations": [
      "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
      "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
      "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
      "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
    ],
    "kind": "final",
    "result": {
      "unit": "percentage_points",
      "value": "2.757665967870018967554982530"
    },
    "state_id": "finance_qa_vnext_state:d4a9278d456543a5fc18e1f889726d08ef6400cd24ca818e9079101eb964cfd6"
  },
  "id": "finance_qa_vnext_final:52da2aecf949a2cf706ca093113229801fa1234df9f01531c522cf29adaeee59",
  "qa_validation": {
    "answer_valid": true,
    "citation_valid": true,
    "id": "finance_qa_vnext_qa_validation:ec6e9158b1afb51653049749b58c34acd3ded1215fbdd505d2af6d9619f9c769",
    "qa_valid": true,
    "reference_program_used_for_callback": false,
    "schema_valid": true,
    "schema_version": "finance_qa_vnext_qa_validation.v2",
    "source_binding_id": "finance_qa_vnext_source_binding:7b861d44d54bafd078e1dc81e679a3c60b559e65a929615badbbf707832b23e7",
    "source_valid": true,
    "task_id": "task:52858dad45af3542780f9d712516b7f6737fe6b2b43c2fb4dc71f16c7a8c85a2"
  },
  "schema_version": "finance_qa_vnext_final.v2",
  "submission_id": "finance_qa_vnext_submission:f75dbd4828d26e21736edb8e082355ef3be617a41e8a3637d016c9cccd3976ac"
}
```

</details>

## 执行顺序总览

| 步骤 | 提交类型 | 操作或处置 | 准入结果 |
| --- | --- | --- | --- |
| [T1](#t1) | action | lookup | 准入 |
| [T2](#t2) | update | accept | 准入 |
| [T3](#t3) | action | lookup | 准入 |
| [T4](#t4) | update | accept | 准入 |
| [T5](#t5) | action | growth | 未准入：admission.public_judgment |
| [T6](#t6) | action | growth | 准入 |
| [T7](#t7) | update | accept | 准入 |
| [T8](#t8) | action | lookup | 准入 |
| [T9](#t9) | update | accept | 准入 |
| [T10](#t10) | action | lookup | 准入 |
| [T11](#t11) | update | accept | 准入 |
| [T12](#t12) | action | growth | 准入 |
| [T13](#t13) | update | accept | 准入 |
| [T14](#t14) | action | signed_percentage_point_gap | 准入 |
| [T15](#t15) | update | accept | 准入 |
| [T16](#t16) | action | absolute_percentage_point_gap | 准入 |
| [T17](#t17) | update | accept | 准入 |
| [T18](#t18) | final | 提交答案 | 准入 |

## 公开证据

以下为同一任务的实际证据对象，包含数值、定义及来源定位。


<details>
<summary>1：revenue</summary>

```json
{
  "assertion_id": "assertion:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
  "definition": {
    "attributes": {
      "comparability_level": "exact_archive_table_cell",
      "default_unit": "million USD",
      "period_type": "duration",
      "source_row_label": "Net sales",
      "statement_type": "income_statement"
    },
    "definition_id": "finance_archive_revenue.v1",
    "text": "Archive-normalized revenue financial statement cell."
  },
  "domain": "finance",
  "domain_context": {
    "archive_grounded": true,
    "benchmark_distribution_weight": null,
    "economic_period_sort_key": 2015,
    "is_forecast": false,
    "period_type": "duration",
    "statement_type": "income_statement"
  },
  "epistemic_status": "observed",
  "evidence_id": "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
  "evidence_kind": "scalar_observation",
  "evidence_version_id": "version:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e@v1",
  "extraction_confidence": 1.0,
  "payload": {
    "currency": "USD",
    "kind": "scalar_observation",
    "precision": null,
    "unit": "million USD",
    "value": "12988.7"
  },
  "predicate": "revenue",
  "provenance": {
    "adapter_id": "qa_frozen_finqa_table_adapter.v1",
    "archive_id": "qa_frozen_finqa_source_archive:831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc",
    "build_ids": {
      "archive_sha256": "831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc"
    },
    "content_hash": "f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
    "extraction_method": "exact_table_cell_selector",
    "parent_evidence_ids": [],
    "source_record_id": "CDW/2017/page_38.pdf-1"
  },
  "scope": {
    "attributes": {},
    "label": "CDW Corporation consolidated",
    "scope_id": "finqa:CDW",
    "scope_type": "consolidated_entity"
  },
  "source": {
    "attributes": {
      "distribution_inference_authorized": false
    },
    "authority": "curated_database",
    "license_note": "Existing repository-frozen research benchmark snapshot",
    "name": "FinQA frozen test financial-document source Archive",
    "provider": "FinQA",
    "source_id": "qa_frozen_finqa_source_archive:831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc"
  },
  "source_locator": {
    "bounding_box": null,
    "char_end": null,
    "char_start": null,
    "document_version": "831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc",
    "json_pointer": "/CDW/2017/page_38.pdf-1/table_ori/2/3",
    "page": 38,
    "quoted_text_hash": "03721e1f01ac668e1ddb52bf68159a9c48caa2aee0722b83e06fc123440eb681",
    "raw_object_id": "qa_frozen_finqa_source_archive:831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc:CDW/2017/page_38.pdf-1",
    "row": "Net sales",
    "source_document_id": "CDW/2017/page_38.pdf",
    "storage_uri": "trusted_data_synthesis/benchmarks/finqa/frozen/test.json",
    "table": "table_ori",
    "table_cell": "R2C3",
    "text_span": null,
    "uri": null
  },
  "subject": {
    "attributes": {
      "ticker": "CDW"
    },
    "name": "CDW Corporation",
    "subject_id": "finqa:CDW",
    "subject_type": "public_company"
  },
  "temporal_context": {
    "basis": "fiscal_period",
    "frequency": "annual",
    "label": "FY2015",
    "observed_at": null,
    "published_at": null,
    "retrieved_at": null,
    "valid_from": "2015-01-01",
    "valid_to": "2015-12-31"
  }
}
```

</details>


<details>
<summary>2：revenue</summary>

```json
{
  "assertion_id": "assertion:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
  "definition": {
    "attributes": {
      "comparability_level": "exact_archive_table_cell",
      "default_unit": "million USD",
      "period_type": "duration",
      "source_row_label": "Net sales",
      "statement_type": "income_statement"
    },
    "definition_id": "finance_archive_revenue.v1",
    "text": "Archive-normalized revenue financial statement cell."
  },
  "domain": "finance",
  "domain_context": {
    "archive_grounded": true,
    "benchmark_distribution_weight": null,
    "economic_period_sort_key": 2016,
    "is_forecast": false,
    "period_type": "duration",
    "statement_type": "income_statement"
  },
  "epistemic_status": "observed",
  "evidence_id": "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
  "evidence_kind": "scalar_observation",
  "evidence_version_id": "version:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43@v1",
  "extraction_confidence": 1.0,
  "payload": {
    "currency": "USD",
    "kind": "scalar_observation",
    "precision": null,
    "unit": "million USD",
    "value": "13981.9"
  },
  "predicate": "revenue",
  "provenance": {
    "adapter_id": "qa_frozen_finqa_table_adapter.v1",
    "archive_id": "qa_frozen_finqa_source_archive:831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc",
    "build_ids": {
      "archive_sha256": "831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc"
    },
    "content_hash": "20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
    "extraction_method": "exact_table_cell_selector",
    "parent_evidence_ids": [],
    "source_record_id": "CDW/2017/page_38.pdf-1"
  },
  "scope": {
    "attributes": {},
    "label": "CDW Corporation consolidated",
    "scope_id": "finqa:CDW",
    "scope_type": "consolidated_entity"
  },
  "source": {
    "attributes": {
      "distribution_inference_authorized": false
    },
    "authority": "curated_database",
    "license_note": "Existing repository-frozen research benchmark snapshot",
    "name": "FinQA frozen test financial-document source Archive",
    "provider": "FinQA",
    "source_id": "qa_frozen_finqa_source_archive:831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc"
  },
  "source_locator": {
    "bounding_box": null,
    "char_end": null,
    "char_start": null,
    "document_version": "831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc",
    "json_pointer": "/CDW/2017/page_38.pdf-1/table_ori/2/2",
    "page": 38,
    "quoted_text_hash": "621253707e7daa87f9dbfc1af0676bcc6f930291773eaf84d76b53b214afbd2c",
    "raw_object_id": "qa_frozen_finqa_source_archive:831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc:CDW/2017/page_38.pdf-1",
    "row": "Net sales",
    "source_document_id": "CDW/2017/page_38.pdf",
    "storage_uri": "trusted_data_synthesis/benchmarks/finqa/frozen/test.json",
    "table": "table_ori",
    "table_cell": "R2C2",
    "text_span": null,
    "uri": null
  },
  "subject": {
    "attributes": {
      "ticker": "CDW"
    },
    "name": "CDW Corporation",
    "subject_id": "finqa:CDW",
    "subject_type": "public_company"
  },
  "temporal_context": {
    "basis": "fiscal_period",
    "frequency": "annual",
    "label": "FY2016",
    "observed_at": null,
    "published_at": null,
    "retrieved_at": null,
    "valid_from": "2016-01-01",
    "valid_to": "2016-12-31"
  }
}
```

</details>


<details>
<summary>3：operating_income</summary>

```json
{
  "assertion_id": "assertion:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
  "definition": {
    "attributes": {
      "comparability_level": "exact_archive_table_cell",
      "default_unit": "million USD",
      "period_type": "duration",
      "source_row_label": "Income from operations",
      "statement_type": "income_statement"
    },
    "definition_id": "finance_archive_operating_income.v1",
    "text": "Archive-normalized operating income financial statement cell."
  },
  "domain": "finance",
  "domain_context": {
    "archive_grounded": true,
    "benchmark_distribution_weight": null,
    "economic_period_sort_key": 2015,
    "is_forecast": false,
    "period_type": "duration",
    "statement_type": "income_statement"
  },
  "epistemic_status": "observed",
  "evidence_id": "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
  "evidence_kind": "scalar_observation",
  "evidence_version_id": "version:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2@v1",
  "extraction_confidence": 1.0,
  "payload": {
    "currency": "USD",
    "kind": "scalar_observation",
    "precision": null,
    "unit": "million USD",
    "value": "742"
  },
  "predicate": "operating_income",
  "provenance": {
    "adapter_id": "qa_frozen_finqa_table_adapter.v1",
    "archive_id": "qa_frozen_finqa_source_archive:831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc",
    "build_ids": {
      "archive_sha256": "831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc"
    },
    "content_hash": "809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
    "extraction_method": "exact_table_cell_selector",
    "parent_evidence_ids": [],
    "source_record_id": "CDW/2017/page_38.pdf-1"
  },
  "scope": {
    "attributes": {},
    "label": "CDW Corporation consolidated",
    "scope_id": "finqa:CDW",
    "scope_type": "consolidated_entity"
  },
  "source": {
    "attributes": {
      "distribution_inference_authorized": false
    },
    "authority": "curated_database",
    "license_note": "Existing repository-frozen research benchmark snapshot",
    "name": "FinQA frozen test financial-document source Archive",
    "provider": "FinQA",
    "source_id": "qa_frozen_finqa_source_archive:831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc"
  },
  "source_locator": {
    "bounding_box": null,
    "char_end": null,
    "char_start": null,
    "document_version": "831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc",
    "json_pointer": "/CDW/2017/page_38.pdf-1/table_ori/4/3",
    "page": 38,
    "quoted_text_hash": "a44c2328e859e06049a7075d65fdc926c060ab418a1a095c4e9961209f1d911e",
    "raw_object_id": "qa_frozen_finqa_source_archive:831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc:CDW/2017/page_38.pdf-1",
    "row": "Income from operations",
    "source_document_id": "CDW/2017/page_38.pdf",
    "storage_uri": "trusted_data_synthesis/benchmarks/finqa/frozen/test.json",
    "table": "table_ori",
    "table_cell": "R4C3",
    "text_span": null,
    "uri": null
  },
  "subject": {
    "attributes": {
      "ticker": "CDW"
    },
    "name": "CDW Corporation",
    "subject_id": "finqa:CDW",
    "subject_type": "public_company"
  },
  "temporal_context": {
    "basis": "fiscal_period",
    "frequency": "annual",
    "label": "FY2015",
    "observed_at": null,
    "published_at": null,
    "retrieved_at": null,
    "valid_from": "2015-01-01",
    "valid_to": "2015-12-31"
  }
}
```

</details>


<details>
<summary>4：operating_income</summary>

```json
{
  "assertion_id": "assertion:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773",
  "definition": {
    "attributes": {
      "comparability_level": "exact_archive_table_cell",
      "default_unit": "million USD",
      "period_type": "duration",
      "source_row_label": "Income from operations",
      "statement_type": "income_statement"
    },
    "definition_id": "finance_archive_operating_income.v1",
    "text": "Archive-normalized operating income financial statement cell."
  },
  "domain": "finance",
  "domain_context": {
    "archive_grounded": true,
    "benchmark_distribution_weight": null,
    "economic_period_sort_key": 2016,
    "is_forecast": false,
    "period_type": "duration",
    "statement_type": "income_statement"
  },
  "epistemic_status": "observed",
  "evidence_id": "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773",
  "evidence_kind": "scalar_observation",
  "evidence_version_id": "version:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773@v1",
  "extraction_confidence": 1.0,
  "payload": {
    "currency": "USD",
    "kind": "scalar_observation",
    "precision": null,
    "unit": "million USD",
    "value": "819.2"
  },
  "predicate": "operating_income",
  "provenance": {
    "adapter_id": "qa_frozen_finqa_table_adapter.v1",
    "archive_id": "qa_frozen_finqa_source_archive:831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc",
    "build_ids": {
      "archive_sha256": "831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc"
    },
    "content_hash": "ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773",
    "extraction_method": "exact_table_cell_selector",
    "parent_evidence_ids": [],
    "source_record_id": "CDW/2017/page_38.pdf-1"
  },
  "scope": {
    "attributes": {},
    "label": "CDW Corporation consolidated",
    "scope_id": "finqa:CDW",
    "scope_type": "consolidated_entity"
  },
  "source": {
    "attributes": {
      "distribution_inference_authorized": false
    },
    "authority": "curated_database",
    "license_note": "Existing repository-frozen research benchmark snapshot",
    "name": "FinQA frozen test financial-document source Archive",
    "provider": "FinQA",
    "source_id": "qa_frozen_finqa_source_archive:831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc"
  },
  "source_locator": {
    "bounding_box": null,
    "char_end": null,
    "char_start": null,
    "document_version": "831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc",
    "json_pointer": "/CDW/2017/page_38.pdf-1/table_ori/4/2",
    "page": 38,
    "quoted_text_hash": "31ef5a2bbb77faf35730f496532112f7d3d4908ee42f9aea9866cd8e9e556a8c",
    "raw_object_id": "qa_frozen_finqa_source_archive:831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc:CDW/2017/page_38.pdf-1",
    "row": "Income from operations",
    "source_document_id": "CDW/2017/page_38.pdf",
    "storage_uri": "trusted_data_synthesis/benchmarks/finqa/frozen/test.json",
    "table": "table_ori",
    "table_cell": "R4C2",
    "text_span": null,
    "uri": null
  },
  "subject": {
    "attributes": {
      "ticker": "CDW"
    },
    "name": "CDW Corporation",
    "subject_id": "finqa:CDW",
    "subject_type": "public_company"
  },
  "temporal_context": {
    "basis": "fiscal_period",
    "frequency": "annual",
    "label": "FY2016",
    "observed_at": null,
    "published_at": null,
    "retrieved_at": null,
    "valid_from": "2016-01-01",
    "valid_to": "2016-12-31"
  }
}
```

</details>


<details>
<summary>展开公开任务与数值条件</summary>

```json
{
  "task": {
    "allowed_tools": [
      "evidence.search",
      "calculator"
    ],
    "answer_schema": {
      "additional_result_properties": false,
      "allow_claims": false,
      "answer_schema_contract_version": "answer_schema_contract.v1",
      "required_fields": [
        "value",
        "unit"
      ],
      "type": "percentage_point_scalar"
    },
    "domain": "finance",
    "instruction": "Across FY2015 to FY2016, what is the absolute percentage-point spread between CDW Corporation's revenue growth and operating-income growth after calculating both growth rates?",
    "level": "research_workflow",
    "metadata": {
      "difficulty_profile": {
        "branch_factor": 1.0,
        "evidence_count": 4.0,
        "graph_depth": 3.0,
        "level": "expert",
        "operation_count": 8.0,
        "pattern_prior_cost": 9.0,
        "pattern_prior_level": "expert",
        "policy_version": "task_difficulty.v2",
        "program_depth": 4.0,
        "semantic_alignment_cost": 4.0,
        "semantic_constraint_count": 5.0,
        "structural_score": 17.75,
        "total_score": 17.75
      },
      "domain_plugin_id": "finance_semantic_depth_three_experiment.v1",
      "experimental_only": true,
      "pattern_catalog": "finance_semantic_depth_three_constructibility.v1",
      "proof_required": true,
      "source_grounding_requirement": "not_applicable",
      "task_pattern": {
        "compiler_version": "task_pattern_compiler.v1",
        "difficulty_base": "expert",
        "difficulty_base_cost": 9.0,
        "pattern_hash": "task_pattern:0d553a0dca8d720694beeec065b9d814e0b2162b971ce97d02f6e5cbd9d083e7",
        "pattern_id": "finance.experimental.derived_growth_absolute_spread",
        "pattern_version": "1.0.0",
        "quality_profile_id": "finance.experimental.depth_three.branch.quality.v1",
        "runtime_id": "finance_semantic_depth_three_pattern_runtime.v1",
        "runtime_version": "1.0.0",
        "schema_version": "task_pattern.v1",
        "semantic_constraint_count": 5
      },
      "topology_kind": "branch_and_merge"
    },
    "planning_track": "plan_given",
    "program_skeleton": {
      "nodes": [
        {
          "dependencies": [],
          "inputs": [
            {
              "kind": "evidence",
              "role_id": "evidence_role_1",
              "selector": null,
              "semantic_constraints": {
                "definition_id": "finance_archive_revenue.v1",
                "epistemic_status": "observed",
                "frequency": "annual",
                "predicate": "revenue",
                "scope_id": "finqa:CDW",
                "scope_type": "consolidated_entity",
                "source_authority": "curated_database",
                "source_name": "FinQA frozen test financial-document source Archive",
                "subject_id": "finqa:CDW",
                "temporal_label": "FY2015",
                "time_basis": "fiscal_period"
              }
            }
          ],
          "operator_id": "lookup",
          "output_schema": "payload",
          "parameters": {},
          "public_node_id": "revenue_earlier_value",
          "tool_capability": null
        },
        {
          "dependencies": [],
          "inputs": [
            {
              "kind": "evidence",
              "role_id": "evidence_role_2",
              "selector": null,
              "semantic_constraints": {
                "definition_id": "finance_archive_revenue.v1",
                "epistemic_status": "observed",
                "frequency": "annual",
                "predicate": "revenue",
                "scope_id": "finqa:CDW",
                "scope_type": "consolidated_entity",
                "source_authority": "curated_database",
                "source_name": "FinQA frozen test financial-document source Archive",
                "subject_id": "finqa:CDW",
                "temporal_label": "FY2016",
                "time_basis": "fiscal_period"
              }
            }
          ],
          "operator_id": "lookup",
          "output_schema": "payload",
          "parameters": {},
          "public_node_id": "revenue_later_value",
          "tool_capability": null
        },
        {
          "dependencies": [],
          "inputs": [
            {
              "kind": "evidence",
              "role_id": "evidence_role_3",
              "selector": null,
              "semantic_constraints": {
                "definition_id": "finance_archive_operating_income.v1",
                "epistemic_status": "observed",
                "frequency": "annual",
                "predicate": "operating_income",
                "scope_id": "finqa:CDW",
                "scope_type": "consolidated_entity",
                "source_authority": "curated_database",
                "source_name": "FinQA frozen test financial-document source Archive",
                "subject_id": "finqa:CDW",
                "temporal_label": "FY2015",
                "time_basis": "fiscal_period"
              }
            }
          ],
          "operator_id": "lookup",
          "output_schema": "payload",
          "parameters": {},
          "public_node_id": "income_earlier_value",
          "tool_capability": null
        },
        {
          "dependencies": [],
          "inputs": [
            {
              "kind": "evidence",
              "role_id": "evidence_role_4",
              "selector": null,
              "semantic_constraints": {
                "definition_id": "finance_archive_operating_income.v1",
                "epistemic_status": "observed",
                "frequency": "annual",
                "predicate": "operating_income",
                "scope_id": "finqa:CDW",
                "scope_type": "consolidated_entity",
                "source_authority": "curated_database",
                "source_name": "FinQA frozen test financial-document source Archive",
                "subject_id": "finqa:CDW",
                "temporal_label": "FY2016",
                "time_basis": "fiscal_period"
              }
            }
          ],
          "operator_id": "lookup",
          "output_schema": "payload",
          "parameters": {},
          "public_node_id": "income_later_value",
          "tool_capability": null
        },
        {
          "dependencies": [
            "revenue_earlier_value",
            "revenue_later_value"
          ],
          "inputs": [
            {
              "kind": "operation",
              "role_id": "revenue_earlier_value",
              "selector": "payload.value",
              "semantic_constraints": {}
            },
            {
              "kind": "operation",
              "role_id": "revenue_later_value",
              "selector": "payload.value",
              "semantic_constraints": {}
            }
          ],
          "operator_id": "growth",
          "output_schema": "percentage",
          "parameters": {},
          "public_node_id": "revenue_growth",
          "tool_capability": "calculator"
        },
        {
          "dependencies": [
            "income_earlier_value",
            "income_later_value"
          ],
          "inputs": [
            {
              "kind": "operation",
              "role_id": "income_earlier_value",
              "selector": "payload.value",
              "semantic_constraints": {}
            },
            {
              "kind": "operation",
              "role_id": "income_later_value",
              "selector": "payload.value",
              "semantic_constraints": {}
            }
          ],
          "operator_id": "growth",
          "output_schema": "percentage",
          "parameters": {},
          "public_node_id": "income_growth",
          "tool_capability": "calculator"
        },
        {
          "dependencies": [
            "income_growth",
            "revenue_growth"
          ],
          "inputs": [
            {
              "kind": "operation",
              "role_id": "income_growth",
              "selector": "value",
              "semantic_constraints": {}
            },
            {
              "kind": "operation",
              "role_id": "revenue_growth",
              "selector": "value",
              "semantic_constraints": {}
            }
          ],
          "operator_id": "signed_percentage_point_gap",
          "output_schema": "scalar",
          "parameters": {},
          "public_node_id": "signed_gap",
          "tool_capability": "calculator"
        },
        {
          "dependencies": [
            "signed_gap"
          ],
          "inputs": [
            {
              "kind": "operation",
              "role_id": "signed_gap",
              "selector": "value",
              "semantic_constraints": {}
            }
          ],
          "operator_id": "absolute_percentage_point_gap",
          "output_schema": "scalar",
          "parameters": {},
          "public_node_id": "result",
          "tool_capability": "calculator"
        }
      ],
      "output_node_id": "result",
      "skeleton_version": "public_program_skeleton.v1"
    },
    "requirements": [
      "retrieve_evidence",
      "select_evidence",
      "cite_source",
      "calculate",
      "verify_result"
    ],
    "retrieval_scope": {
      "predicates": [
        "operating_income",
        "revenue"
      ],
      "semantic_constraints": {
        "definition_ids": [
          "finance_archive_operating_income.v1",
          "finance_archive_revenue.v1"
        ],
        "epistemic_statuses": [
          "observed"
        ],
        "frequencies": [
          "annual"
        ],
        "historical_only": true,
        "payload_contexts": [
          {
            "currency": "USD",
            "unit": "million USD"
          }
        ],
        "scope_ids": [
          "finqa:CDW"
        ],
        "scope_types": [
          "consolidated_entity"
        ],
        "source_authorities": [
          "curated_database"
        ],
        "time_bases": [
          "fiscal_period"
        ]
      },
      "subject_ids": [
        "finqa:CDW"
      ],
      "temporal_labels": [
        "FY2015",
        "FY2016"
      ]
    },
    "retrieval_track": "resolved",
    "task_id": "task:52858dad45af3542780f9d712516b7f6737fe6b2b43c2fb4dc71f16c7a8c85a2",
    "task_type": "derived_growth_absolute_spread"
  },
  "numeric": {
    "applies_to": [
      "registered_operation_execution",
      "independent_operation_verification",
      "public_answer_projection",
      "final_qa"
    ],
    "arithmetic": "decimal",
    "precision": 28,
    "rounding": "ROUND_HALF_EVEN",
    "share_numeric_contract_reused": false
  }
}
```

</details>


## 逐次提交与反馈

动作产生Observation；只有后续准入的Update才建立Claim。未准入的动作不会被写成已执行运算；每次纠正仍独立展示。


<a id="t1"></a>

### T1 — Action / 动作

准入。

模型请求操作：`lookup`。


```json
[
  {
    "kind": "evidence",
    "ref_id": "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
    "role": "evidence_role_1",
    "selector": null
  }
]
```

实际解析输入：


```json
[
  {
    "ref_id": "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
    "value": {
      "currency": "USD",
      "kind": "scalar_observation",
      "precision": null,
      "unit": "million USD",
      "value": "12988.7"
    }
  }
]
```

实际执行输出：


```json
{
  "payload": {
    "currency": "USD",
    "kind": "scalar_observation",
    "unit": "million USD",
    "value": "12988.7"
  },
  "selected_ref": "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"
}
```

提交后实际反馈：


```json
{
  "admitted": true,
  "code": "pending_observation_requires_callback_update"
}
```


<details>
<summary>展开完整模型提交（parsed，保留全部字段）</summary>

```json
{
  "decision": {
    "basis": {
      "claim_refs": [],
      "evidence_refs": [
        "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"
      ],
      "relation": "requires"
    },
    "candidate_action_ids": [
      "finance_qa_vnext_offered_action:b2c9d9b9a4954ac3c269d53c94a5638ebd63f49c9f2da985792e55f948ff6178",
      "finance_qa_vnext_offered_action:f92bd68c0cb60d304a890a56601ba4f2c7497f9f3deef24987d147a239c1a508",
      "finance_qa_vnext_offered_action:6886f62ac273570994c3e771076f3cf852f788da65d061305b6503b7352296e3",
      "finance_qa_vnext_offered_action:41654b7b5f61a5ae032e2075f8317f10fe2be6b16d0e90b42e45c91c5acdf259"
    ],
    "expected_effect": {
      "establishes_obligation": "revenue_earlier_value",
      "output_schema": "payload"
    },
    "obligation_id": "revenue_earlier_value",
    "selected_action_id": "finance_qa_vnext_offered_action:b2c9d9b9a4954ac3c269d53c94a5638ebd63f49c9f2da985792e55f948ff6178",
    "selection_rule": "dependency_ready",
    "subgoal": "resolve_evidence",
    "unresolved_uncertainty_refs": []
  },
  "inputs": [
    {
      "kind": "evidence",
      "ref_id": "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
      "role": "evidence_role_1",
      "selector": null
    }
  ],
  "kind": "action",
  "operation": "lookup",
  "parameters": {},
  "state_id": "finance_qa_vnext_state:faa0ccb964592f1b97361d7c67d012b0265c67cbe08411106ecfe0cdb13543f4"
}
```

</details>


<details>
<summary>展开本次回执、观察及状态引用</summary>

```json
{
  "sequence": 0,
  "request_id": "finance_qa_vnext_request:2ba180a7a2fbce30ff139791b8082e92f7cb57e1f7e0d11825625320dc583a2e",
  "submission": {
    "callback_binding": {
      "automatic_retries": 0,
      "host_semantic_field_fill": false,
      "id": "qa_vnext_model_execution_callback_binding:28b6bf92cda61d05426e665ae1679076194054197f39efde697ead110ef76e21",
      "implementation": {
        "class": "OnlineModelCallback",
        "method": "generate",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport",
        "source_byte_count": 30336,
        "source_relative_path": "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_model_execution/transport.py",
        "source_sha256": "d2b8f3bfc1dcc06fd8e97b87e3d6a438cb7953574876e563f00da3cd2c55bdd0"
      },
      "model_configuration_id": "qa_vnext_model_execution_transport_config:e6869eff1807bc19fc09aff494959508a3b0991169092fd8b2243590148fed9f",
      "model_fallbacks": 0,
      "model_origin_requires_attempt_response_evidence": true,
      "origin": "model",
      "schema_version": "qa_vnext_model_execution_callback_binding.v1",
      "sender_implementation": {
        "class": "HttpxSender",
        "httpx_version": "0.28.1",
        "method": "send",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport"
      },
      "session_id": "qa_vnext_task_panel_session:768b7d5de873286ced2f7dd5a751e26043dea4b51cfb42e4a30780b5fca22574",
      "transport_kind": "live_http"
    },
    "host_repairs": [],
    "id": "finance_qa_vnext_submission:723679611f08198aee69153de16ab826b14c9f3e1df7df020f211cf90a599326",
    "raw_bytes": 1499,
    "raw_sha256": "538dd67bb31529cf889d27439cd8a108d977149796ebcddbab5767345e155afb",
    "request_id": "finance_qa_vnext_request:2ba180a7a2fbce30ff139791b8082e92f7cb57e1f7e0d11825625320dc583a2e",
    "schema_version": "finance_qa_vnext_submission.v2"
  },
  "receipt": {
    "admitted": true,
    "error_code": null,
    "id": "finance_qa_vnext_receipt:59713cde52d78f8855e4818801ff3db8471e472baca3a515b188d74aa8ae6c95",
    "no_host_semantic_repair": true,
    "request_id": "finance_qa_vnext_request:2ba180a7a2fbce30ff139791b8082e92f7cb57e1f7e0d11825625320dc583a2e",
    "schema_version": "finance_qa_vnext_receipt.v2",
    "state_id": "finance_qa_vnext_state:faa0ccb964592f1b97361d7c67d012b0265c67cbe08411106ecfe0cdb13543f4",
    "submission_id": "finance_qa_vnext_submission:723679611f08198aee69153de16ab826b14c9f3e1df7df020f211cf90a599326"
  },
  "observation": {
    "action_submission_id": "finance_qa_vnext_submission:723679611f08198aee69153de16ab826b14c9f3e1df7df020f211cf90a599326",
    "execution_id": "finance_qa_vnext_execution:714a847b8398b1056d5ce65e82111fff7618ab8207b09090ec9ea29287284020",
    "id": "finance_qa_vnext_observation:cb9afd3bd1661b29deda7d49966acbd85793b2e873c69852c155cdb42fb18d32",
    "independent_output_valid": true,
    "obligation_id": "revenue_earlier_value",
    "proposition": {
      "lineage": [
        "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"
      ],
      "operation": "lookup",
      "operation_contract_id": "operation_semantic_contract:5973498aa753de7f23db18e12807d21c8a71baf5af45805d961b3d6134df6417",
      "output": {
        "payload": {
          "currency": "USD",
          "kind": "scalar_observation",
          "unit": "million USD",
          "value": "12988.7"
        },
        "selected_ref": "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"
      }
    },
    "receipt_id": "finance_qa_vnext_receipt:59713cde52d78f8855e4818801ff3db8471e472baca3a515b188d74aa8ae6c95",
    "schema_version": "finance_qa_vnext_observation.v2",
    "selected_action": {
      "alternative_group": "revenue_earlier_value",
      "basis": {
        "claim_refs": [],
        "evidence_refs": [
          "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"
        ],
        "relation": "requires"
      },
      "expected_effect": {
        "establishes_obligation": "revenue_earlier_value",
        "output_schema": "payload"
      },
      "id": "finance_qa_vnext_offered_action:b2c9d9b9a4954ac3c269d53c94a5638ebd63f49c9f2da985792e55f948ff6178",
      "input_order_policy": "ordered",
      "inputs": [
        {
          "kind": "evidence",
          "ref_id": "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
          "role": "evidence_role_1",
          "selector": null
        }
      ],
      "obligation_id": "revenue_earlier_value",
      "operation": "lookup",
      "operation_contract_id": "operation_semantic_contract:5973498aa753de7f23db18e12807d21c8a71baf5af45805d961b3d6134df6417",
      "parameters": {},
      "schema_version": "finance_qa_vnext_offered_action.v2",
      "selection_rules": [
        "dependency_ready",
        "registered_semantic_preconditions"
      ],
      "semantic_choice": [
        "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"
      ],
      "subgoal": "resolve_evidence"
    }
  },
  "post_state_id": "finance_qa_vnext_state:52d737217ec39404431b0702671089a470f64b447b776d2a695d45d39aa0645a"
}
```

</details>


<a id="t2"></a>

### T2 — Update / 接受或拒绝观察

准入。

模型处置：`accept`；后续子目标：`revenue_later_value`。

实际建立Claim：`finance_qa_vnext_claim:7fa4d5c72ab102562d3a5fe110cfc627d36b2142fd48c4736961c2c1ed6b3c98`。


```json
{
  "lineage": [
    "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"
  ],
  "operation": "lookup",
  "operation_contract_id": "operation_semantic_contract:5973498aa753de7f23db18e12807d21c8a71baf5af45805d961b3d6134df6417",
  "output": {
    "payload": {
      "currency": "USD",
      "kind": "scalar_observation",
      "unit": "million USD",
      "value": "12988.7"
    },
    "selected_ref": "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"
  }
}
```

提交后实际反馈：


```json
{
  "admitted": true,
  "code": "claim_accepted"
}
```


<details>
<summary>展开完整模型提交（parsed，保留全部字段）</summary>

```json
{
  "assessment": {
    "evidence_refs": [
      "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"
    ],
    "fulfills_obligation": "revenue_earlier_value",
    "observation_refs": [
      "finance_qa_vnext_observation:cb9afd3bd1661b29deda7d49966acbd85793b2e873c69852c155cdb42fb18d32"
    ],
    "relation": "accepts_observed_proposition"
  },
  "disposition": "accept",
  "kind": "update",
  "newly_enabled_obligation_ids": [],
  "next_subgoal": "revenue_later_value",
  "observation_id": "finance_qa_vnext_observation:cb9afd3bd1661b29deda7d49966acbd85793b2e873c69852c155cdb42fb18d32",
  "proposed_claim": {
    "lineage": [
      "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"
    ],
    "operation": "lookup",
    "operation_contract_id": "operation_semantic_contract:5973498aa753de7f23db18e12807d21c8a71baf5af45805d961b3d6134df6417",
    "output": {
      "payload": {
        "currency": "USD",
        "kind": "scalar_observation",
        "unit": "million USD",
        "value": "12988.7"
      },
      "selected_ref": "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"
    }
  },
  "remaining_uncertainty_refs": [],
  "state_id": "finance_qa_vnext_state:52d737217ec39404431b0702671089a470f64b447b776d2a695d45d39aa0645a"
}
```

</details>


<details>
<summary>展开本次回执、观察及状态引用</summary>

```json
{
  "sequence": 1,
  "request_id": "finance_qa_vnext_request:e05441fa22b9d875c5a9771cb3c88dc0ecd7cdf8c7f22803450ce3d685e115c6",
  "submission": {
    "callback_binding": {
      "automatic_retries": 0,
      "host_semantic_field_fill": false,
      "id": "qa_vnext_model_execution_callback_binding:28b6bf92cda61d05426e665ae1679076194054197f39efde697ead110ef76e21",
      "implementation": {
        "class": "OnlineModelCallback",
        "method": "generate",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport",
        "source_byte_count": 30336,
        "source_relative_path": "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_model_execution/transport.py",
        "source_sha256": "d2b8f3bfc1dcc06fd8e97b87e3d6a438cb7953574876e563f00da3cd2c55bdd0"
      },
      "model_configuration_id": "qa_vnext_model_execution_transport_config:e6869eff1807bc19fc09aff494959508a3b0991169092fd8b2243590148fed9f",
      "model_fallbacks": 0,
      "model_origin_requires_attempt_response_evidence": true,
      "origin": "model",
      "schema_version": "qa_vnext_model_execution_callback_binding.v1",
      "sender_implementation": {
        "class": "HttpxSender",
        "httpx_version": "0.28.1",
        "method": "send",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport"
      },
      "session_id": "qa_vnext_task_panel_session:768b7d5de873286ced2f7dd5a751e26043dea4b51cfb42e4a30780b5fca22574",
      "transport_kind": "live_http"
    },
    "host_repairs": [],
    "id": "finance_qa_vnext_submission:6426cd114af6d8aca5561d06674125ffff17c1230af106820bb88c2f3ef36b1a",
    "raw_bytes": 1368,
    "raw_sha256": "4dc79d05717d81582bf5b1292cc87407fae023a0992f310b485acf12b8f3c057",
    "request_id": "finance_qa_vnext_request:e05441fa22b9d875c5a9771cb3c88dc0ecd7cdf8c7f22803450ce3d685e115c6",
    "schema_version": "finance_qa_vnext_submission.v2"
  },
  "receipt": {
    "admitted": true,
    "error_code": null,
    "id": "finance_qa_vnext_receipt:3efb57fbe1637cc847cf9038be450ceeb62d89aa22ff0faf1362d2c1f858b349",
    "no_host_semantic_repair": true,
    "request_id": "finance_qa_vnext_request:e05441fa22b9d875c5a9771cb3c88dc0ecd7cdf8c7f22803450ce3d685e115c6",
    "schema_version": "finance_qa_vnext_receipt.v2",
    "state_id": "finance_qa_vnext_state:52d737217ec39404431b0702671089a470f64b447b776d2a695d45d39aa0645a",
    "submission_id": "finance_qa_vnext_submission:6426cd114af6d8aca5561d06674125ffff17c1230af106820bb88c2f3ef36b1a"
  },
  "observation": null,
  "post_state_id": "finance_qa_vnext_state:fbbdd8ecf3882bf70e729ddb5df3b23c5dd13fcee83d7cd1ce173c2399a0e693"
}
```

</details>


<a id="t3"></a>

### T3 — Action / 动作

准入。

模型请求操作：`lookup`。


```json
[
  {
    "kind": "evidence",
    "ref_id": "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
    "role": "evidence_role_2",
    "selector": null
  }
]
```

实际解析输入：


```json
[
  {
    "ref_id": "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
    "value": {
      "currency": "USD",
      "kind": "scalar_observation",
      "precision": null,
      "unit": "million USD",
      "value": "13981.9"
    }
  }
]
```

实际执行输出：


```json
{
  "payload": {
    "currency": "USD",
    "kind": "scalar_observation",
    "unit": "million USD",
    "value": "13981.9"
  },
  "selected_ref": "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43"
}
```

提交后实际反馈：


```json
{
  "admitted": true,
  "code": "pending_observation_requires_callback_update"
}
```


<details>
<summary>展开完整模型提交（parsed，保留全部字段）</summary>

```json
{
  "decision": {
    "basis": {
      "claim_refs": [],
      "evidence_refs": [
        "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43"
      ],
      "relation": "requires"
    },
    "candidate_action_ids": [
      "finance_qa_vnext_offered_action:f92bd68c0cb60d304a890a56601ba4f2c7497f9f3deef24987d147a239c1a508",
      "finance_qa_vnext_offered_action:6886f62ac273570994c3e771076f3cf852f788da65d061305b6503b7352296e3",
      "finance_qa_vnext_offered_action:41654b7b5f61a5ae032e2075f8317f10fe2be6b16d0e90b42e45c91c5acdf259"
    ],
    "expected_effect": {
      "establishes_obligation": "revenue_later_value",
      "output_schema": "payload"
    },
    "obligation_id": "revenue_later_value",
    "selected_action_id": "finance_qa_vnext_offered_action:f92bd68c0cb60d304a890a56601ba4f2c7497f9f3deef24987d147a239c1a508",
    "selection_rule": "dependency_ready",
    "subgoal": "resolve_evidence",
    "unresolved_uncertainty_refs": []
  },
  "inputs": [
    {
      "kind": "evidence",
      "ref_id": "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
      "role": "evidence_role_2",
      "selector": null
    }
  ],
  "kind": "action",
  "operation": "lookup",
  "parameters": {},
  "state_id": "finance_qa_vnext_state:fbbdd8ecf3882bf70e729ddb5df3b23c5dd13fcee83d7cd1ce173c2399a0e693"
}
```

</details>


<details>
<summary>展开本次回执、观察及状态引用</summary>

```json
{
  "sequence": 2,
  "request_id": "finance_qa_vnext_request:253d51677bd8a511f955a086a44d39a3c26bbcb65148e0c791bd78715bac8aee",
  "submission": {
    "callback_binding": {
      "automatic_retries": 0,
      "host_semantic_field_fill": false,
      "id": "qa_vnext_model_execution_callback_binding:28b6bf92cda61d05426e665ae1679076194054197f39efde697ead110ef76e21",
      "implementation": {
        "class": "OnlineModelCallback",
        "method": "generate",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport",
        "source_byte_count": 30336,
        "source_relative_path": "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_model_execution/transport.py",
        "source_sha256": "d2b8f3bfc1dcc06fd8e97b87e3d6a438cb7953574876e563f00da3cd2c55bdd0"
      },
      "model_configuration_id": "qa_vnext_model_execution_transport_config:e6869eff1807bc19fc09aff494959508a3b0991169092fd8b2243590148fed9f",
      "model_fallbacks": 0,
      "model_origin_requires_attempt_response_evidence": true,
      "origin": "model",
      "schema_version": "qa_vnext_model_execution_callback_binding.v1",
      "sender_implementation": {
        "class": "HttpxSender",
        "httpx_version": "0.28.1",
        "method": "send",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport"
      },
      "session_id": "qa_vnext_task_panel_session:768b7d5de873286ced2f7dd5a751e26043dea4b51cfb42e4a30780b5fca22574",
      "transport_kind": "live_http"
    },
    "host_repairs": [],
    "id": "finance_qa_vnext_submission:f0c630c0852b2af7932061b238b243d4a875ebdaacb1a48a594b2913056e40f1",
    "raw_bytes": 1389,
    "raw_sha256": "f287c782853621d86c9a0c337bc59111228e748d7d00df881ecb8b3de5c25719",
    "request_id": "finance_qa_vnext_request:253d51677bd8a511f955a086a44d39a3c26bbcb65148e0c791bd78715bac8aee",
    "schema_version": "finance_qa_vnext_submission.v2"
  },
  "receipt": {
    "admitted": true,
    "error_code": null,
    "id": "finance_qa_vnext_receipt:c33db21ccb0ac4e92fff25efc016f59ba6a737c71fd5e2cb24ef527b45659617",
    "no_host_semantic_repair": true,
    "request_id": "finance_qa_vnext_request:253d51677bd8a511f955a086a44d39a3c26bbcb65148e0c791bd78715bac8aee",
    "schema_version": "finance_qa_vnext_receipt.v2",
    "state_id": "finance_qa_vnext_state:fbbdd8ecf3882bf70e729ddb5df3b23c5dd13fcee83d7cd1ce173c2399a0e693",
    "submission_id": "finance_qa_vnext_submission:f0c630c0852b2af7932061b238b243d4a875ebdaacb1a48a594b2913056e40f1"
  },
  "observation": {
    "action_submission_id": "finance_qa_vnext_submission:f0c630c0852b2af7932061b238b243d4a875ebdaacb1a48a594b2913056e40f1",
    "execution_id": "finance_qa_vnext_execution:294ee8342573e809d5d8838d0f40d6f4ba6d5bb42e7985a505241635c497746e",
    "id": "finance_qa_vnext_observation:e8e61129b92e3920a5896dfb90549858e99325769f1c7eb1697eb8a02e717792",
    "independent_output_valid": true,
    "obligation_id": "revenue_later_value",
    "proposition": {
      "lineage": [
        "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43"
      ],
      "operation": "lookup",
      "operation_contract_id": "operation_semantic_contract:5973498aa753de7f23db18e12807d21c8a71baf5af45805d961b3d6134df6417",
      "output": {
        "payload": {
          "currency": "USD",
          "kind": "scalar_observation",
          "unit": "million USD",
          "value": "13981.9"
        },
        "selected_ref": "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43"
      }
    },
    "receipt_id": "finance_qa_vnext_receipt:c33db21ccb0ac4e92fff25efc016f59ba6a737c71fd5e2cb24ef527b45659617",
    "schema_version": "finance_qa_vnext_observation.v2",
    "selected_action": {
      "alternative_group": "revenue_later_value",
      "basis": {
        "claim_refs": [],
        "evidence_refs": [
          "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43"
        ],
        "relation": "requires"
      },
      "expected_effect": {
        "establishes_obligation": "revenue_later_value",
        "output_schema": "payload"
      },
      "id": "finance_qa_vnext_offered_action:f92bd68c0cb60d304a890a56601ba4f2c7497f9f3deef24987d147a239c1a508",
      "input_order_policy": "ordered",
      "inputs": [
        {
          "kind": "evidence",
          "ref_id": "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
          "role": "evidence_role_2",
          "selector": null
        }
      ],
      "obligation_id": "revenue_later_value",
      "operation": "lookup",
      "operation_contract_id": "operation_semantic_contract:5973498aa753de7f23db18e12807d21c8a71baf5af45805d961b3d6134df6417",
      "parameters": {},
      "schema_version": "finance_qa_vnext_offered_action.v2",
      "selection_rules": [
        "dependency_ready",
        "registered_semantic_preconditions"
      ],
      "semantic_choice": [
        "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43"
      ],
      "subgoal": "resolve_evidence"
    }
  },
  "post_state_id": "finance_qa_vnext_state:2a3e948d3e942fddd582d923c9db0b73be1b0fe7199dae64a1c36ee9b7bd1cc0"
}
```

</details>


<a id="t4"></a>

### T4 — Update / 接受或拒绝观察

准入。

模型处置：`accept`；后续子目标：`revenue_growth`。

实际建立Claim：`finance_qa_vnext_claim:9e67f06231641bbaadfcf76ad550c58f849cf619ded47ac64c42117bd88f7f51`。


```json
{
  "lineage": [
    "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43"
  ],
  "operation": "lookup",
  "operation_contract_id": "operation_semantic_contract:5973498aa753de7f23db18e12807d21c8a71baf5af45805d961b3d6134df6417",
  "output": {
    "payload": {
      "currency": "USD",
      "kind": "scalar_observation",
      "unit": "million USD",
      "value": "13981.9"
    },
    "selected_ref": "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43"
  }
}
```

提交后实际反馈：


```json
{
  "admitted": true,
  "code": "claim_accepted"
}
```


<details>
<summary>展开完整模型提交（parsed，保留全部字段）</summary>

```json
{
  "assessment": {
    "evidence_refs": [
      "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43"
    ],
    "fulfills_obligation": "revenue_later_value",
    "observation_refs": [
      "finance_qa_vnext_observation:e8e61129b92e3920a5896dfb90549858e99325769f1c7eb1697eb8a02e717792"
    ],
    "relation": "accepts_observed_proposition"
  },
  "disposition": "accept",
  "kind": "update",
  "newly_enabled_obligation_ids": [
    "revenue_growth"
  ],
  "next_subgoal": "revenue_growth",
  "observation_id": "finance_qa_vnext_observation:e8e61129b92e3920a5896dfb90549858e99325769f1c7eb1697eb8a02e717792",
  "proposed_claim": {
    "lineage": [
      "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43"
    ],
    "operation": "lookup",
    "operation_contract_id": "operation_semantic_contract:5973498aa753de7f23db18e12807d21c8a71baf5af45805d961b3d6134df6417",
    "output": {
      "payload": {
        "currency": "USD",
        "kind": "scalar_observation",
        "unit": "million USD",
        "value": "13981.9"
      },
      "selected_ref": "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43"
    }
  },
  "remaining_uncertainty_refs": [],
  "state_id": "finance_qa_vnext_state:2a3e948d3e942fddd582d923c9db0b73be1b0fe7199dae64a1c36ee9b7bd1cc0"
}
```

</details>


<details>
<summary>展开本次回执、观察及状态引用</summary>

```json
{
  "sequence": 3,
  "request_id": "finance_qa_vnext_request:2ee57cf3fcb40c7f45b01d36354fd91fd32b83025d9c9e7cc3f37bcabb5e1066",
  "submission": {
    "callback_binding": {
      "automatic_retries": 0,
      "host_semantic_field_fill": false,
      "id": "qa_vnext_model_execution_callback_binding:28b6bf92cda61d05426e665ae1679076194054197f39efde697ead110ef76e21",
      "implementation": {
        "class": "OnlineModelCallback",
        "method": "generate",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport",
        "source_byte_count": 30336,
        "source_relative_path": "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_model_execution/transport.py",
        "source_sha256": "d2b8f3bfc1dcc06fd8e97b87e3d6a438cb7953574876e563f00da3cd2c55bdd0"
      },
      "model_configuration_id": "qa_vnext_model_execution_transport_config:e6869eff1807bc19fc09aff494959508a3b0991169092fd8b2243590148fed9f",
      "model_fallbacks": 0,
      "model_origin_requires_attempt_response_evidence": true,
      "origin": "model",
      "schema_version": "qa_vnext_model_execution_callback_binding.v1",
      "sender_implementation": {
        "class": "HttpxSender",
        "httpx_version": "0.28.1",
        "method": "send",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport"
      },
      "session_id": "qa_vnext_task_panel_session:768b7d5de873286ced2f7dd5a751e26043dea4b51cfb42e4a30780b5fca22574",
      "transport_kind": "live_http"
    },
    "host_repairs": [],
    "id": "finance_qa_vnext_submission:f628200e5466da897a6c18fe1fdc48480d91d8995c61ad22ea923923e034d379",
    "raw_bytes": 1385,
    "raw_sha256": "534d0c0aca6255a2c885e61acfb1992bf8a5f5cb3f36eefc768ca371095e279e",
    "request_id": "finance_qa_vnext_request:2ee57cf3fcb40c7f45b01d36354fd91fd32b83025d9c9e7cc3f37bcabb5e1066",
    "schema_version": "finance_qa_vnext_submission.v2"
  },
  "receipt": {
    "admitted": true,
    "error_code": null,
    "id": "finance_qa_vnext_receipt:747a60fe3e9099c1bd71ecd26573ea06dd9a9474f4ddc30315a52553adf16ea9",
    "no_host_semantic_repair": true,
    "request_id": "finance_qa_vnext_request:2ee57cf3fcb40c7f45b01d36354fd91fd32b83025d9c9e7cc3f37bcabb5e1066",
    "schema_version": "finance_qa_vnext_receipt.v2",
    "state_id": "finance_qa_vnext_state:2a3e948d3e942fddd582d923c9db0b73be1b0fe7199dae64a1c36ee9b7bd1cc0",
    "submission_id": "finance_qa_vnext_submission:f628200e5466da897a6c18fe1fdc48480d91d8995c61ad22ea923923e034d379"
  },
  "observation": null,
  "post_state_id": "finance_qa_vnext_state:787437984f8f9614d8164cafa56a8c5fb66650c3c3469aa58b12dc9c1b290167"
}
```

</details>


<a id="t5"></a>

### T5 — Action / 动作

**未准入**：`admission.public_judgment`。

模型请求操作：`growth`。


```json
[
  {
    "kind": "claim",
    "ref_id": "finance_qa_vnext_claim:7fa4d5c72ab102562d3a5fe110cfc627d36b2142fd48c4736961c2c1ed6b3c98",
    "role": "revenue_earlier_value",
    "selector": "payload.value"
  },
  {
    "kind": "claim",
    "ref_id": "finance_qa_vnext_claim:9e67f06231641bbaadfcf76ad550c58f849cf619ded47ac64c42117bd88f7f51",
    "role": "revenue_later_value",
    "selector": "payload.value"
  }
]
```

本次没有执行结果。

提交后实际反馈：


```json
{
  "admitted": false,
  "code": "admission.public_judgment",
  "public_diagnostic": {
    "action_selected_by_host": false,
    "contract_id": "finance_qa_vnext_action_public_contract:fe48fd87bdf017de09f3091503230f48a83ce4ece83faf20e0c06dedec6baff8",
    "public_source_mapping": {
      "/decision/basis": {
        "copy_from_selected": "/basis"
      },
      "/decision/expected_effect": {
        "copy_from_selected": "/expected_effect"
      },
      "/decision/obligation_id": {
        "copy_from_selected": "/obligation_id"
      },
      "/decision/selection_rule": {
        "choose_from_selected": "/selection_rules"
      },
      "/decision/subgoal": {
        "copy_from_selected": "/subgoal"
      },
      "/decision/unresolved_uncertainty_refs": {
        "literal": []
      }
    },
    "requirement": "obligation_id, subgoal, basis and expected_effect must come from that SAME selected Action. Use one of its selection_rules; unresolved_uncertainty_refs must be []. basis and expected_effect use canonical JSON equality including all arrays in their given order.",
    "response_field_paths": [
      "/decision/basis"
    ],
    "response_rewritten": false,
    "rule_id": "finance_qa_action_public_contract.v1:public_judgment",
    "selected_binding": {
      "id_field": "id",
      "match_count": 1,
      "request_collection": "/available_actions",
      "response_selector": "/decision/selected_action_id"
    },
    "version": "finance_qa_action_public_contract.v1"
  }
}
```


<details>
<summary>展开完整模型提交（parsed，保留全部字段）</summary>

```json
{
  "decision": {
    "basis": {
      "claim_refs": [
        "finance_qa_vnext_claim:7fa4d5c72ab102562d3a5fe110cfc627d36b2142fd48c4736961c2c1ed6b3c98",
        "finance_qa_vnext_claim:9e67f06231641bbaadfcf76ad550c58f849cf619ded47ac64c42117bd88f7f51"
      ],
      "evidence_refs": [],
      "relation": "requires"
    },
    "candidate_action_ids": [
      "finance_qa_vnext_offered_action:6886f62ac273570994c3e771076f3cf852f788da65d061305b6503b7352296e3",
      "finance_qa_vnext_offered_action:41654b7b5f61a5ae032e2075f8317f10fe2be6b16d0e90b42e45c91c5acdf259",
      "finance_qa_vnext_offered_action:5caba9618f6d380c6832e46ae0a76cdfc3e9a1cc63ad32c43cb88802c51bf53b"
    ],
    "expected_effect": {
      "establishes_obligation": "revenue_growth",
      "output_schema": "percentage"
    },
    "obligation_id": "revenue_growth",
    "selected_action_id": "finance_qa_vnext_offered_action:5caba9618f6d380c6832e46ae0a76cdfc3e9a1cc63ad32c43cb88802c51bf53b",
    "selection_rule": "dependency_ready",
    "subgoal": "derive_quantity",
    "unresolved_uncertainty_refs": []
  },
  "inputs": [
    {
      "kind": "claim",
      "ref_id": "finance_qa_vnext_claim:7fa4d5c72ab102562d3a5fe110cfc627d36b2142fd48c4736961c2c1ed6b3c98",
      "role": "revenue_earlier_value",
      "selector": "payload.value"
    },
    {
      "kind": "claim",
      "ref_id": "finance_qa_vnext_claim:9e67f06231641bbaadfcf76ad550c58f849cf619ded47ac64c42117bd88f7f51",
      "role": "revenue_later_value",
      "selector": "payload.value"
    }
  ],
  "kind": "action",
  "operation": "growth",
  "parameters": {},
  "state_id": "finance_qa_vnext_state:787437984f8f9614d8164cafa56a8c5fb66650c3c3469aa58b12dc9c1b290167"
}
```

</details>


<details>
<summary>展开本次回执、观察及状态引用</summary>

```json
{
  "sequence": 4,
  "request_id": "finance_qa_vnext_request:cf49fbe62ac9c889f7b92e18384effddb06e246bc2fe46ba98f289fc38404239",
  "submission": {
    "callback_binding": {
      "automatic_retries": 0,
      "host_semantic_field_fill": false,
      "id": "qa_vnext_model_execution_callback_binding:28b6bf92cda61d05426e665ae1679076194054197f39efde697ead110ef76e21",
      "implementation": {
        "class": "OnlineModelCallback",
        "method": "generate",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport",
        "source_byte_count": 30336,
        "source_relative_path": "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_model_execution/transport.py",
        "source_sha256": "d2b8f3bfc1dcc06fd8e97b87e3d6a438cb7953574876e563f00da3cd2c55bdd0"
      },
      "model_configuration_id": "qa_vnext_model_execution_transport_config:e6869eff1807bc19fc09aff494959508a3b0991169092fd8b2243590148fed9f",
      "model_fallbacks": 0,
      "model_origin_requires_attempt_response_evidence": true,
      "origin": "model",
      "schema_version": "qa_vnext_model_execution_callback_binding.v1",
      "sender_implementation": {
        "class": "HttpxSender",
        "httpx_version": "0.28.1",
        "method": "send",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport"
      },
      "session_id": "qa_vnext_task_panel_session:768b7d5de873286ced2f7dd5a751e26043dea4b51cfb42e4a30780b5fca22574",
      "transport_kind": "live_http"
    },
    "host_repairs": [],
    "id": "finance_qa_vnext_submission:2f6bd639d9381a06a233650da4b5bcc38bcd7b31a00211895ff5c773cd829be0",
    "raw_bytes": 1698,
    "raw_sha256": "c1dafd67511882b5e67c2e28d999aa830c72a1dafb62731901e382c3b28f183c",
    "request_id": "finance_qa_vnext_request:cf49fbe62ac9c889f7b92e18384effddb06e246bc2fe46ba98f289fc38404239",
    "schema_version": "finance_qa_vnext_submission.v2"
  },
  "receipt": {
    "admitted": false,
    "error_code": "admission.public_judgment",
    "id": "finance_qa_vnext_receipt:49bd3462a08bb42a90e97413bd47900303b5892f2e2b27a5a5b924d79ac6a2e8",
    "no_host_semantic_repair": true,
    "request_id": "finance_qa_vnext_request:cf49fbe62ac9c889f7b92e18384effddb06e246bc2fe46ba98f289fc38404239",
    "schema_version": "finance_qa_vnext_receipt.v2",
    "state_id": "finance_qa_vnext_state:787437984f8f9614d8164cafa56a8c5fb66650c3c3469aa58b12dc9c1b290167",
    "submission_id": "finance_qa_vnext_submission:2f6bd639d9381a06a233650da4b5bcc38bcd7b31a00211895ff5c773cd829be0"
  },
  "observation": null,
  "post_state_id": "finance_qa_vnext_state:ce09f88adc5de4173341e4c045a8213463165cbbb6dce6f80a31dd1ffd1b5f0e"
}
```

</details>


<a id="t6"></a>

### T6 — Action / 动作

准入。

模型请求操作：`growth`。


```json
[
  {
    "kind": "claim",
    "ref_id": "finance_qa_vnext_claim:7fa4d5c72ab102562d3a5fe110cfc627d36b2142fd48c4736961c2c1ed6b3c98",
    "role": "revenue_earlier_value",
    "selector": "payload.value"
  },
  {
    "kind": "claim",
    "ref_id": "finance_qa_vnext_claim:9e67f06231641bbaadfcf76ad550c58f849cf619ded47ac64c42117bd88f7f51",
    "role": "revenue_later_value",
    "selector": "payload.value"
  }
]
```

实际解析输入：


```json
[
  {
    "ref_id": "revenue_earlier_value",
    "value": "12988.7"
  },
  {
    "ref_id": "revenue_later_value",
    "value": "13981.9"
  }
]
```

实际执行输出：


```json
{
  "value": "7.646646700593592892283292400"
}
```

提交后实际反馈：


```json
{
  "admitted": true,
  "code": "pending_observation_requires_callback_update"
}
```


<details>
<summary>展开完整模型提交（parsed，保留全部字段）</summary>

```json
{
  "decision": {
    "basis": {
      "claim_refs": [
        "finance_qa_vnext_claim:7fa4d5c72ab102562d3a5fe110cfc627d36b2142fd48c4736961c2c1ed6b3c98",
        "finance_qa_vnext_claim:9e67f06231641bbaadfcf76ad550c58f849cf619ded47ac64c42117bd88f7f51"
      ],
      "evidence_refs": [
        "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
        "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"
      ],
      "relation": "requires"
    },
    "candidate_action_ids": [
      "finance_qa_vnext_offered_action:6886f62ac273570994c3e771076f3cf852f788da65d061305b6503b7352296e3",
      "finance_qa_vnext_offered_action:41654b7b5f61a5ae032e2075f8317f10fe2be6b16d0e90b42e45c91c5acdf259",
      "finance_qa_vnext_offered_action:5caba9618f6d380c6832e46ae0a76cdfc3e9a1cc63ad32c43cb88802c51bf53b"
    ],
    "expected_effect": {
      "establishes_obligation": "revenue_growth",
      "output_schema": "percentage"
    },
    "obligation_id": "revenue_growth",
    "selected_action_id": "finance_qa_vnext_offered_action:5caba9618f6d380c6832e46ae0a76cdfc3e9a1cc63ad32c43cb88802c51bf53b",
    "selection_rule": "dependency_ready",
    "subgoal": "derive_quantity",
    "unresolved_uncertainty_refs": []
  },
  "inputs": [
    {
      "kind": "claim",
      "ref_id": "finance_qa_vnext_claim:7fa4d5c72ab102562d3a5fe110cfc627d36b2142fd48c4736961c2c1ed6b3c98",
      "role": "revenue_earlier_value",
      "selector": "payload.value"
    },
    {
      "kind": "claim",
      "ref_id": "finance_qa_vnext_claim:9e67f06231641bbaadfcf76ad550c58f849cf619ded47ac64c42117bd88f7f51",
      "role": "revenue_later_value",
      "selector": "payload.value"
    }
  ],
  "kind": "action",
  "operation": "growth",
  "parameters": {},
  "state_id": "finance_qa_vnext_state:ce09f88adc5de4173341e4c045a8213463165cbbb6dce6f80a31dd1ffd1b5f0e"
}
```

</details>


<details>
<summary>展开本次回执、观察及状态引用</summary>

```json
{
  "sequence": 5,
  "request_id": "finance_qa_vnext_request:dd9fc0a6ec448340d578b2a620b4bfc5122de9f32cc0ecc6712f6f8710181c28",
  "submission": {
    "callback_binding": {
      "automatic_retries": 0,
      "host_semantic_field_fill": false,
      "id": "qa_vnext_model_execution_callback_binding:28b6bf92cda61d05426e665ae1679076194054197f39efde697ead110ef76e21",
      "implementation": {
        "class": "OnlineModelCallback",
        "method": "generate",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport",
        "source_byte_count": 30336,
        "source_relative_path": "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_model_execution/transport.py",
        "source_sha256": "d2b8f3bfc1dcc06fd8e97b87e3d6a438cb7953574876e563f00da3cd2c55bdd0"
      },
      "model_configuration_id": "qa_vnext_model_execution_transport_config:e6869eff1807bc19fc09aff494959508a3b0991169092fd8b2243590148fed9f",
      "model_fallbacks": 0,
      "model_origin_requires_attempt_response_evidence": true,
      "origin": "model",
      "schema_version": "qa_vnext_model_execution_callback_binding.v1",
      "sender_implementation": {
        "class": "HttpxSender",
        "httpx_version": "0.28.1",
        "method": "send",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport"
      },
      "session_id": "qa_vnext_task_panel_session:768b7d5de873286ced2f7dd5a751e26043dea4b51cfb42e4a30780b5fca22574",
      "transport_kind": "live_http"
    },
    "host_repairs": [],
    "id": "finance_qa_vnext_submission:f28e0a4b582ce04e85a5b1108b9c3f670247971a4c86ac65b4cab6f4d14eea33",
    "raw_bytes": 1912,
    "raw_sha256": "c09f1ec2ebc94e014dd22c4b2609b4716dcbca281767797c4efbfd7549c8730d",
    "request_id": "finance_qa_vnext_request:dd9fc0a6ec448340d578b2a620b4bfc5122de9f32cc0ecc6712f6f8710181c28",
    "schema_version": "finance_qa_vnext_submission.v2"
  },
  "receipt": {
    "admitted": true,
    "error_code": null,
    "id": "finance_qa_vnext_receipt:590a03d598da588579e5650a3f629e45c096647b5584ecd33d11c28a3772d0d6",
    "no_host_semantic_repair": true,
    "request_id": "finance_qa_vnext_request:dd9fc0a6ec448340d578b2a620b4bfc5122de9f32cc0ecc6712f6f8710181c28",
    "schema_version": "finance_qa_vnext_receipt.v2",
    "state_id": "finance_qa_vnext_state:ce09f88adc5de4173341e4c045a8213463165cbbb6dce6f80a31dd1ffd1b5f0e",
    "submission_id": "finance_qa_vnext_submission:f28e0a4b582ce04e85a5b1108b9c3f670247971a4c86ac65b4cab6f4d14eea33"
  },
  "observation": {
    "action_submission_id": "finance_qa_vnext_submission:f28e0a4b582ce04e85a5b1108b9c3f670247971a4c86ac65b4cab6f4d14eea33",
    "execution_id": "finance_qa_vnext_execution:f4a0a535071371bf8f754b2f68c16fc053931f7b1c4f57c962484256bd6ae2c8",
    "id": "finance_qa_vnext_observation:513f1ac40ae96c7d1098efaa5444c6a9321bf4cec38452c0981db4c8487fd425",
    "independent_output_valid": true,
    "obligation_id": "revenue_growth",
    "proposition": {
      "lineage": [
        "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
        "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"
      ],
      "operation": "growth",
      "operation_contract_id": "operation_semantic_contract:01c784c5ca5f8800bfba52102d3c585fa040eb5b20a0529c7e0b8d303ebe9e5b",
      "output": {
        "value": "7.646646700593592892283292400"
      }
    },
    "receipt_id": "finance_qa_vnext_receipt:590a03d598da588579e5650a3f629e45c096647b5584ecd33d11c28a3772d0d6",
    "schema_version": "finance_qa_vnext_observation.v2",
    "selected_action": {
      "alternative_group": "revenue_growth",
      "basis": {
        "claim_refs": [
          "finance_qa_vnext_claim:7fa4d5c72ab102562d3a5fe110cfc627d36b2142fd48c4736961c2c1ed6b3c98",
          "finance_qa_vnext_claim:9e67f06231641bbaadfcf76ad550c58f849cf619ded47ac64c42117bd88f7f51"
        ],
        "evidence_refs": [
          "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
          "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"
        ],
        "relation": "requires"
      },
      "expected_effect": {
        "establishes_obligation": "revenue_growth",
        "output_schema": "percentage"
      },
      "id": "finance_qa_vnext_offered_action:5caba9618f6d380c6832e46ae0a76cdfc3e9a1cc63ad32c43cb88802c51bf53b",
      "input_order_policy": "ordered",
      "inputs": [
        {
          "kind": "claim",
          "ref_id": "finance_qa_vnext_claim:7fa4d5c72ab102562d3a5fe110cfc627d36b2142fd48c4736961c2c1ed6b3c98",
          "role": "revenue_earlier_value",
          "selector": "payload.value"
        },
        {
          "kind": "claim",
          "ref_id": "finance_qa_vnext_claim:9e67f06231641bbaadfcf76ad550c58f849cf619ded47ac64c42117bd88f7f51",
          "role": "revenue_later_value",
          "selector": "payload.value"
        }
      ],
      "obligation_id": "revenue_growth",
      "operation": "growth",
      "operation_contract_id": "operation_semantic_contract:01c784c5ca5f8800bfba52102d3c585fa040eb5b20a0529c7e0b8d303ebe9e5b",
      "parameters": {},
      "schema_version": "finance_qa_vnext_offered_action.v2",
      "selection_rules": [
        "dependency_ready",
        "registered_semantic_preconditions"
      ],
      "semantic_choice": [],
      "subgoal": "derive_quantity"
    }
  },
  "post_state_id": "finance_qa_vnext_state:4ae19eb39eb53dde292927ec44363476d0cd3548347b8c8f6ecf3aa96859112d"
}
```

</details>


<a id="t7"></a>

### T7 — Update / 接受或拒绝观察

准入。

模型处置：`accept`；后续子目标：`income_earlier_value`。

实际建立Claim：`finance_qa_vnext_claim:8cfc88648e868e6fee287a8496cf04db79430e2d29f4f41a5f3ce0eb671c993d`。


```json
{
  "lineage": [
    "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
    "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"
  ],
  "operation": "growth",
  "operation_contract_id": "operation_semantic_contract:01c784c5ca5f8800bfba52102d3c585fa040eb5b20a0529c7e0b8d303ebe9e5b",
  "output": {
    "value": "7.646646700593592892283292400"
  }
}
```

提交后实际反馈：


```json
{
  "admitted": true,
  "code": "claim_accepted"
}
```


<details>
<summary>展开完整模型提交（parsed，保留全部字段）</summary>

```json
{
  "assessment": {
    "evidence_refs": [
      "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
      "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"
    ],
    "fulfills_obligation": "revenue_growth",
    "observation_refs": [
      "finance_qa_vnext_observation:513f1ac40ae96c7d1098efaa5444c6a9321bf4cec38452c0981db4c8487fd425"
    ],
    "relation": "accepts_observed_proposition"
  },
  "disposition": "accept",
  "kind": "update",
  "newly_enabled_obligation_ids": [],
  "next_subgoal": "income_earlier_value",
  "observation_id": "finance_qa_vnext_observation:513f1ac40ae96c7d1098efaa5444c6a9321bf4cec38452c0981db4c8487fd425",
  "proposed_claim": {
    "lineage": [
      "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
      "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e"
    ],
    "operation": "growth",
    "operation_contract_id": "operation_semantic_contract:01c784c5ca5f8800bfba52102d3c585fa040eb5b20a0529c7e0b8d303ebe9e5b",
    "output": {
      "value": "7.646646700593592892283292400"
    }
  },
  "remaining_uncertainty_refs": [],
  "state_id": "finance_qa_vnext_state:4ae19eb39eb53dde292927ec44363476d0cd3548347b8c8f6ecf3aa96859112d"
}
```

</details>


<details>
<summary>展开本次回执、观察及状态引用</summary>

```json
{
  "sequence": 6,
  "request_id": "finance_qa_vnext_request:bf58bbb696b911975018500cfe4f74cd91949337cc8ca20fe3e84e67093ea197",
  "submission": {
    "callback_binding": {
      "automatic_retries": 0,
      "host_semantic_field_fill": false,
      "id": "qa_vnext_model_execution_callback_binding:28b6bf92cda61d05426e665ae1679076194054197f39efde697ead110ef76e21",
      "implementation": {
        "class": "OnlineModelCallback",
        "method": "generate",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport",
        "source_byte_count": 30336,
        "source_relative_path": "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_model_execution/transport.py",
        "source_sha256": "d2b8f3bfc1dcc06fd8e97b87e3d6a438cb7953574876e563f00da3cd2c55bdd0"
      },
      "model_configuration_id": "qa_vnext_model_execution_transport_config:e6869eff1807bc19fc09aff494959508a3b0991169092fd8b2243590148fed9f",
      "model_fallbacks": 0,
      "model_origin_requires_attempt_response_evidence": true,
      "origin": "model",
      "schema_version": "qa_vnext_model_execution_callback_binding.v1",
      "sender_implementation": {
        "class": "HttpxSender",
        "httpx_version": "0.28.1",
        "method": "send",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport"
      },
      "session_id": "qa_vnext_task_panel_session:768b7d5de873286ced2f7dd5a751e26043dea4b51cfb42e4a30780b5fca22574",
      "transport_kind": "live_http"
    },
    "host_repairs": [],
    "id": "finance_qa_vnext_submission:80f721f2a5228843b2e9181030838cae253b19c8b29436b695d08bd6801718ab",
    "raw_bytes": 1345,
    "raw_sha256": "588573cf3b547f0d61ab66acb03cd503477366101b9b8a479aaf6ac028037c78",
    "request_id": "finance_qa_vnext_request:bf58bbb696b911975018500cfe4f74cd91949337cc8ca20fe3e84e67093ea197",
    "schema_version": "finance_qa_vnext_submission.v2"
  },
  "receipt": {
    "admitted": true,
    "error_code": null,
    "id": "finance_qa_vnext_receipt:b6cbd9a84bc5f9451d3e4428832674a172ab8f9c6046dde77e82f1dfb907ebb0",
    "no_host_semantic_repair": true,
    "request_id": "finance_qa_vnext_request:bf58bbb696b911975018500cfe4f74cd91949337cc8ca20fe3e84e67093ea197",
    "schema_version": "finance_qa_vnext_receipt.v2",
    "state_id": "finance_qa_vnext_state:4ae19eb39eb53dde292927ec44363476d0cd3548347b8c8f6ecf3aa96859112d",
    "submission_id": "finance_qa_vnext_submission:80f721f2a5228843b2e9181030838cae253b19c8b29436b695d08bd6801718ab"
  },
  "observation": null,
  "post_state_id": "finance_qa_vnext_state:4e9680ea9e513f7e0b23d03d149668fdde6dfbb90b6d3109e75787dcf4c1fe6b"
}
```

</details>


<a id="t8"></a>

### T8 — Action / 动作

准入。

模型请求操作：`lookup`。


```json
[
  {
    "kind": "evidence",
    "ref_id": "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
    "role": "evidence_role_3",
    "selector": null
  }
]
```

实际解析输入：


```json
[
  {
    "ref_id": "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
    "value": {
      "currency": "USD",
      "kind": "scalar_observation",
      "precision": null,
      "unit": "million USD",
      "value": "742"
    }
  }
]
```

实际执行输出：


```json
{
  "payload": {
    "currency": "USD",
    "kind": "scalar_observation",
    "unit": "million USD",
    "value": "742"
  },
  "selected_ref": "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2"
}
```

提交后实际反馈：


```json
{
  "admitted": true,
  "code": "pending_observation_requires_callback_update"
}
```


<details>
<summary>展开完整模型提交（parsed，保留全部字段）</summary>

```json
{
  "decision": {
    "basis": {
      "claim_refs": [],
      "evidence_refs": [
        "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2"
      ],
      "relation": "requires"
    },
    "candidate_action_ids": [
      "finance_qa_vnext_offered_action:6886f62ac273570994c3e771076f3cf852f788da65d061305b6503b7352296e3",
      "finance_qa_vnext_offered_action:41654b7b5f61a5ae032e2075f8317f10fe2be6b16d0e90b42e45c91c5acdf259"
    ],
    "expected_effect": {
      "establishes_obligation": "income_earlier_value",
      "output_schema": "payload"
    },
    "obligation_id": "income_earlier_value",
    "selected_action_id": "finance_qa_vnext_offered_action:6886f62ac273570994c3e771076f3cf852f788da65d061305b6503b7352296e3",
    "selection_rule": "dependency_ready",
    "subgoal": "resolve_evidence",
    "unresolved_uncertainty_refs": []
  },
  "inputs": [
    {
      "kind": "evidence",
      "ref_id": "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
      "role": "evidence_role_3",
      "selector": null
    }
  ],
  "kind": "action",
  "operation": "lookup",
  "parameters": {},
  "state_id": "finance_qa_vnext_state:4e9680ea9e513f7e0b23d03d149668fdde6dfbb90b6d3109e75787dcf4c1fe6b"
}
```

</details>


<details>
<summary>展开本次回执、观察及状态引用</summary>

```json
{
  "sequence": 7,
  "request_id": "finance_qa_vnext_request:01fcef305aba9ef32715fca14c6eefb0cea0aebc70582185a9256e6067b666d3",
  "submission": {
    "callback_binding": {
      "automatic_retries": 0,
      "host_semantic_field_fill": false,
      "id": "qa_vnext_model_execution_callback_binding:28b6bf92cda61d05426e665ae1679076194054197f39efde697ead110ef76e21",
      "implementation": {
        "class": "OnlineModelCallback",
        "method": "generate",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport",
        "source_byte_count": 30336,
        "source_relative_path": "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_model_execution/transport.py",
        "source_sha256": "d2b8f3bfc1dcc06fd8e97b87e3d6a438cb7953574876e563f00da3cd2c55bdd0"
      },
      "model_configuration_id": "qa_vnext_model_execution_transport_config:e6869eff1807bc19fc09aff494959508a3b0991169092fd8b2243590148fed9f",
      "model_fallbacks": 0,
      "model_origin_requires_attempt_response_evidence": true,
      "origin": "model",
      "schema_version": "qa_vnext_model_execution_callback_binding.v1",
      "sender_implementation": {
        "class": "HttpxSender",
        "httpx_version": "0.28.1",
        "method": "send",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport"
      },
      "session_id": "qa_vnext_task_panel_session:768b7d5de873286ced2f7dd5a751e26043dea4b51cfb42e4a30780b5fca22574",
      "transport_kind": "live_http"
    },
    "host_repairs": [],
    "id": "finance_qa_vnext_submission:e92096b3eb9c7986dd1fb0c39e72e1007e5c9cb64c27a19d2cba280694e2b917",
    "raw_bytes": 1285,
    "raw_sha256": "80cbf4ee478d77b9366054602acb20f0658a3cfd955e6161769b902fec80e095",
    "request_id": "finance_qa_vnext_request:01fcef305aba9ef32715fca14c6eefb0cea0aebc70582185a9256e6067b666d3",
    "schema_version": "finance_qa_vnext_submission.v2"
  },
  "receipt": {
    "admitted": true,
    "error_code": null,
    "id": "finance_qa_vnext_receipt:a4ff644985fbddf9dbae06e6b0d4d0b81adfd64b889fef637ba06a676452ce70",
    "no_host_semantic_repair": true,
    "request_id": "finance_qa_vnext_request:01fcef305aba9ef32715fca14c6eefb0cea0aebc70582185a9256e6067b666d3",
    "schema_version": "finance_qa_vnext_receipt.v2",
    "state_id": "finance_qa_vnext_state:4e9680ea9e513f7e0b23d03d149668fdde6dfbb90b6d3109e75787dcf4c1fe6b",
    "submission_id": "finance_qa_vnext_submission:e92096b3eb9c7986dd1fb0c39e72e1007e5c9cb64c27a19d2cba280694e2b917"
  },
  "observation": {
    "action_submission_id": "finance_qa_vnext_submission:e92096b3eb9c7986dd1fb0c39e72e1007e5c9cb64c27a19d2cba280694e2b917",
    "execution_id": "finance_qa_vnext_execution:22006759da514f24850e0a0568729b33844d0f05bea56937ea45a2dd3e0848b8",
    "id": "finance_qa_vnext_observation:4e7c1d9af684fc3091cee46531e1aee6370e837733a4a202216471c5ff4aea8f",
    "independent_output_valid": true,
    "obligation_id": "income_earlier_value",
    "proposition": {
      "lineage": [
        "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2"
      ],
      "operation": "lookup",
      "operation_contract_id": "operation_semantic_contract:5973498aa753de7f23db18e12807d21c8a71baf5af45805d961b3d6134df6417",
      "output": {
        "payload": {
          "currency": "USD",
          "kind": "scalar_observation",
          "unit": "million USD",
          "value": "742"
        },
        "selected_ref": "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2"
      }
    },
    "receipt_id": "finance_qa_vnext_receipt:a4ff644985fbddf9dbae06e6b0d4d0b81adfd64b889fef637ba06a676452ce70",
    "schema_version": "finance_qa_vnext_observation.v2",
    "selected_action": {
      "alternative_group": "income_earlier_value",
      "basis": {
        "claim_refs": [],
        "evidence_refs": [
          "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2"
        ],
        "relation": "requires"
      },
      "expected_effect": {
        "establishes_obligation": "income_earlier_value",
        "output_schema": "payload"
      },
      "id": "finance_qa_vnext_offered_action:6886f62ac273570994c3e771076f3cf852f788da65d061305b6503b7352296e3",
      "input_order_policy": "ordered",
      "inputs": [
        {
          "kind": "evidence",
          "ref_id": "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
          "role": "evidence_role_3",
          "selector": null
        }
      ],
      "obligation_id": "income_earlier_value",
      "operation": "lookup",
      "operation_contract_id": "operation_semantic_contract:5973498aa753de7f23db18e12807d21c8a71baf5af45805d961b3d6134df6417",
      "parameters": {},
      "schema_version": "finance_qa_vnext_offered_action.v2",
      "selection_rules": [
        "dependency_ready",
        "registered_semantic_preconditions"
      ],
      "semantic_choice": [
        "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2"
      ],
      "subgoal": "resolve_evidence"
    }
  },
  "post_state_id": "finance_qa_vnext_state:238b7b052aaac2f29b83e8569f2ca68534b44906dff24b8aca3cc0a0187fc1de"
}
```

</details>


<a id="t9"></a>

### T9 — Update / 接受或拒绝观察

准入。

模型处置：`accept`；后续子目标：`income_later_value`。

实际建立Claim：`finance_qa_vnext_claim:c7460dbb8c8021d71e81b13e991a4c5c47d775369ff618577e993b5f0f8fe5bd`。


```json
{
  "lineage": [
    "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2"
  ],
  "operation": "lookup",
  "operation_contract_id": "operation_semantic_contract:5973498aa753de7f23db18e12807d21c8a71baf5af45805d961b3d6134df6417",
  "output": {
    "payload": {
      "currency": "USD",
      "kind": "scalar_observation",
      "unit": "million USD",
      "value": "742"
    },
    "selected_ref": "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2"
  }
}
```

提交后实际反馈：


```json
{
  "admitted": true,
  "code": "claim_accepted"
}
```


<details>
<summary>展开完整模型提交（parsed，保留全部字段）</summary>

```json
{
  "assessment": {
    "evidence_refs": [
      "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2"
    ],
    "fulfills_obligation": "income_earlier_value",
    "observation_refs": [
      "finance_qa_vnext_observation:4e7c1d9af684fc3091cee46531e1aee6370e837733a4a202216471c5ff4aea8f"
    ],
    "relation": "accepts_observed_proposition"
  },
  "disposition": "accept",
  "kind": "update",
  "newly_enabled_obligation_ids": [],
  "next_subgoal": "income_later_value",
  "observation_id": "finance_qa_vnext_observation:4e7c1d9af684fc3091cee46531e1aee6370e837733a4a202216471c5ff4aea8f",
  "proposed_claim": {
    "lineage": [
      "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2"
    ],
    "operation": "lookup",
    "operation_contract_id": "operation_semantic_contract:5973498aa753de7f23db18e12807d21c8a71baf5af45805d961b3d6134df6417",
    "output": {
      "payload": {
        "currency": "USD",
        "kind": "scalar_observation",
        "unit": "million USD",
        "value": "742"
      },
      "selected_ref": "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2"
    }
  },
  "remaining_uncertainty_refs": [],
  "state_id": "finance_qa_vnext_state:238b7b052aaac2f29b83e8569f2ca68534b44906dff24b8aca3cc0a0187fc1de"
}
```

</details>


<details>
<summary>展开本次回执、观察及状态引用</summary>

```json
{
  "sequence": 8,
  "request_id": "finance_qa_vnext_request:26cbb7a60b4925c2997267d9b70e47ac217bbcfc941419519c330319e3580c05",
  "submission": {
    "callback_binding": {
      "automatic_retries": 0,
      "host_semantic_field_fill": false,
      "id": "qa_vnext_model_execution_callback_binding:28b6bf92cda61d05426e665ae1679076194054197f39efde697ead110ef76e21",
      "implementation": {
        "class": "OnlineModelCallback",
        "method": "generate",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport",
        "source_byte_count": 30336,
        "source_relative_path": "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_model_execution/transport.py",
        "source_sha256": "d2b8f3bfc1dcc06fd8e97b87e3d6a438cb7953574876e563f00da3cd2c55bdd0"
      },
      "model_configuration_id": "qa_vnext_model_execution_transport_config:e6869eff1807bc19fc09aff494959508a3b0991169092fd8b2243590148fed9f",
      "model_fallbacks": 0,
      "model_origin_requires_attempt_response_evidence": true,
      "origin": "model",
      "schema_version": "qa_vnext_model_execution_callback_binding.v1",
      "sender_implementation": {
        "class": "HttpxSender",
        "httpx_version": "0.28.1",
        "method": "send",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport"
      },
      "session_id": "qa_vnext_task_panel_session:768b7d5de873286ced2f7dd5a751e26043dea4b51cfb42e4a30780b5fca22574",
      "transport_kind": "live_http"
    },
    "host_repairs": [],
    "id": "finance_qa_vnext_submission:5c3419b4c8521734ef32a969fd5391de8494082eef42682900668e108f277fd4",
    "raw_bytes": 1362,
    "raw_sha256": "1a06704c752f870a4704b0fedbc09a76c0f4df285b4f39ec0a9fd1a0623e4c7d",
    "request_id": "finance_qa_vnext_request:26cbb7a60b4925c2997267d9b70e47ac217bbcfc941419519c330319e3580c05",
    "schema_version": "finance_qa_vnext_submission.v2"
  },
  "receipt": {
    "admitted": true,
    "error_code": null,
    "id": "finance_qa_vnext_receipt:5390819d8568b3069c8bbf2f90e0819f35d3dfae73a64b47460309593b489032",
    "no_host_semantic_repair": true,
    "request_id": "finance_qa_vnext_request:26cbb7a60b4925c2997267d9b70e47ac217bbcfc941419519c330319e3580c05",
    "schema_version": "finance_qa_vnext_receipt.v2",
    "state_id": "finance_qa_vnext_state:238b7b052aaac2f29b83e8569f2ca68534b44906dff24b8aca3cc0a0187fc1de",
    "submission_id": "finance_qa_vnext_submission:5c3419b4c8521734ef32a969fd5391de8494082eef42682900668e108f277fd4"
  },
  "observation": null,
  "post_state_id": "finance_qa_vnext_state:d2875bcc25c6e39826e6ad7bd1b8454eac965b9d0ddf30e492afe0323adda8c5"
}
```

</details>


<a id="t10"></a>

### T10 — Action / 动作

准入。

模型请求操作：`lookup`。


```json
[
  {
    "kind": "evidence",
    "ref_id": "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773",
    "role": "evidence_role_4",
    "selector": null
  }
]
```

实际解析输入：


```json
[
  {
    "ref_id": "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773",
    "value": {
      "currency": "USD",
      "kind": "scalar_observation",
      "precision": null,
      "unit": "million USD",
      "value": "819.2"
    }
  }
]
```

实际执行输出：


```json
{
  "payload": {
    "currency": "USD",
    "kind": "scalar_observation",
    "unit": "million USD",
    "value": "819.2"
  },
  "selected_ref": "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
}
```

提交后实际反馈：


```json
{
  "admitted": true,
  "code": "pending_observation_requires_callback_update"
}
```


<details>
<summary>展开完整模型提交（parsed，保留全部字段）</summary>

```json
{
  "decision": {
    "basis": {
      "claim_refs": [],
      "evidence_refs": [
        "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
      ],
      "relation": "requires"
    },
    "candidate_action_ids": [
      "finance_qa_vnext_offered_action:41654b7b5f61a5ae032e2075f8317f10fe2be6b16d0e90b42e45c91c5acdf259"
    ],
    "expected_effect": {
      "establishes_obligation": "income_later_value",
      "output_schema": "payload"
    },
    "obligation_id": "income_later_value",
    "selected_action_id": "finance_qa_vnext_offered_action:41654b7b5f61a5ae032e2075f8317f10fe2be6b16d0e90b42e45c91c5acdf259",
    "selection_rule": "dependency_ready",
    "subgoal": "resolve_evidence",
    "unresolved_uncertainty_refs": []
  },
  "inputs": [
    {
      "kind": "evidence",
      "ref_id": "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773",
      "role": "evidence_role_4",
      "selector": null
    }
  ],
  "kind": "action",
  "operation": "lookup",
  "parameters": {},
  "state_id": "finance_qa_vnext_state:d2875bcc25c6e39826e6ad7bd1b8454eac965b9d0ddf30e492afe0323adda8c5"
}
```

</details>


<details>
<summary>展开本次回执、观察及状态引用</summary>

```json
{
  "sequence": 9,
  "request_id": "finance_qa_vnext_request:f10c077632c935d9811040cb1771c1d0e152246a4be75422215cfb228511c677",
  "submission": {
    "callback_binding": {
      "automatic_retries": 0,
      "host_semantic_field_fill": false,
      "id": "qa_vnext_model_execution_callback_binding:28b6bf92cda61d05426e665ae1679076194054197f39efde697ead110ef76e21",
      "implementation": {
        "class": "OnlineModelCallback",
        "method": "generate",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport",
        "source_byte_count": 30336,
        "source_relative_path": "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_model_execution/transport.py",
        "source_sha256": "d2b8f3bfc1dcc06fd8e97b87e3d6a438cb7953574876e563f00da3cd2c55bdd0"
      },
      "model_configuration_id": "qa_vnext_model_execution_transport_config:e6869eff1807bc19fc09aff494959508a3b0991169092fd8b2243590148fed9f",
      "model_fallbacks": 0,
      "model_origin_requires_attempt_response_evidence": true,
      "origin": "model",
      "schema_version": "qa_vnext_model_execution_callback_binding.v1",
      "sender_implementation": {
        "class": "HttpxSender",
        "httpx_version": "0.28.1",
        "method": "send",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport"
      },
      "session_id": "qa_vnext_task_panel_session:768b7d5de873286ced2f7dd5a751e26043dea4b51cfb42e4a30780b5fca22574",
      "transport_kind": "live_http"
    },
    "host_repairs": [],
    "id": "finance_qa_vnext_submission:747678137ba745dabd9bb0d9761f63faa0b74ec87e7839768d04d66396a07c05",
    "raw_bytes": 1175,
    "raw_sha256": "32767b1d3710b8622a9e0695b3781b0b8d9cccb51080f6034cd41cf52ef48b16",
    "request_id": "finance_qa_vnext_request:f10c077632c935d9811040cb1771c1d0e152246a4be75422215cfb228511c677",
    "schema_version": "finance_qa_vnext_submission.v2"
  },
  "receipt": {
    "admitted": true,
    "error_code": null,
    "id": "finance_qa_vnext_receipt:30ff1e63bc793b4042a0a7d5c662984adfe8a827cf266cf5be8911731bc88a63",
    "no_host_semantic_repair": true,
    "request_id": "finance_qa_vnext_request:f10c077632c935d9811040cb1771c1d0e152246a4be75422215cfb228511c677",
    "schema_version": "finance_qa_vnext_receipt.v2",
    "state_id": "finance_qa_vnext_state:d2875bcc25c6e39826e6ad7bd1b8454eac965b9d0ddf30e492afe0323adda8c5",
    "submission_id": "finance_qa_vnext_submission:747678137ba745dabd9bb0d9761f63faa0b74ec87e7839768d04d66396a07c05"
  },
  "observation": {
    "action_submission_id": "finance_qa_vnext_submission:747678137ba745dabd9bb0d9761f63faa0b74ec87e7839768d04d66396a07c05",
    "execution_id": "finance_qa_vnext_execution:d7138300c90b57a5d27fd1e8777cb64fa3a01189eaa46c1331ddbeeda95ea72e",
    "id": "finance_qa_vnext_observation:83dd7db6009749c52fff7cfc17a7d41769f8b5de2faeac198ba64baee7442614",
    "independent_output_valid": true,
    "obligation_id": "income_later_value",
    "proposition": {
      "lineage": [
        "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
      ],
      "operation": "lookup",
      "operation_contract_id": "operation_semantic_contract:5973498aa753de7f23db18e12807d21c8a71baf5af45805d961b3d6134df6417",
      "output": {
        "payload": {
          "currency": "USD",
          "kind": "scalar_observation",
          "unit": "million USD",
          "value": "819.2"
        },
        "selected_ref": "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
      }
    },
    "receipt_id": "finance_qa_vnext_receipt:30ff1e63bc793b4042a0a7d5c662984adfe8a827cf266cf5be8911731bc88a63",
    "schema_version": "finance_qa_vnext_observation.v2",
    "selected_action": {
      "alternative_group": "income_later_value",
      "basis": {
        "claim_refs": [],
        "evidence_refs": [
          "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
        ],
        "relation": "requires"
      },
      "expected_effect": {
        "establishes_obligation": "income_later_value",
        "output_schema": "payload"
      },
      "id": "finance_qa_vnext_offered_action:41654b7b5f61a5ae032e2075f8317f10fe2be6b16d0e90b42e45c91c5acdf259",
      "input_order_policy": "ordered",
      "inputs": [
        {
          "kind": "evidence",
          "ref_id": "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773",
          "role": "evidence_role_4",
          "selector": null
        }
      ],
      "obligation_id": "income_later_value",
      "operation": "lookup",
      "operation_contract_id": "operation_semantic_contract:5973498aa753de7f23db18e12807d21c8a71baf5af45805d961b3d6134df6417",
      "parameters": {},
      "schema_version": "finance_qa_vnext_offered_action.v2",
      "selection_rules": [
        "dependency_ready",
        "registered_semantic_preconditions"
      ],
      "semantic_choice": [
        "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
      ],
      "subgoal": "resolve_evidence"
    }
  },
  "post_state_id": "finance_qa_vnext_state:dc3aa3dd7e0c980c89092e6965708111890d041767b19cff932591c6b7e73a37"
}
```

</details>


<a id="t11"></a>

### T11 — Update / 接受或拒绝观察

准入。

模型处置：`accept`；后续子目标：`income_growth`。

实际建立Claim：`finance_qa_vnext_claim:6e15b03b2ecaa1642b993e223c15faddaf4e90ab3d7ee35f9443b94fa38227d4`。


```json
{
  "lineage": [
    "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
  ],
  "operation": "lookup",
  "operation_contract_id": "operation_semantic_contract:5973498aa753de7f23db18e12807d21c8a71baf5af45805d961b3d6134df6417",
  "output": {
    "payload": {
      "currency": "USD",
      "kind": "scalar_observation",
      "unit": "million USD",
      "value": "819.2"
    },
    "selected_ref": "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
  }
}
```

提交后实际反馈：


```json
{
  "admitted": true,
  "code": "claim_accepted"
}
```


<details>
<summary>展开完整模型提交（parsed，保留全部字段）</summary>

```json
{
  "assessment": {
    "evidence_refs": [
      "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
    ],
    "fulfills_obligation": "income_later_value",
    "observation_refs": [
      "finance_qa_vnext_observation:83dd7db6009749c52fff7cfc17a7d41769f8b5de2faeac198ba64baee7442614"
    ],
    "relation": "accepts_observed_proposition"
  },
  "disposition": "accept",
  "kind": "update",
  "newly_enabled_obligation_ids": [
    "income_growth"
  ],
  "next_subgoal": "income_growth",
  "observation_id": "finance_qa_vnext_observation:83dd7db6009749c52fff7cfc17a7d41769f8b5de2faeac198ba64baee7442614",
  "proposed_claim": {
    "lineage": [
      "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
    ],
    "operation": "lookup",
    "operation_contract_id": "operation_semantic_contract:5973498aa753de7f23db18e12807d21c8a71baf5af45805d961b3d6134df6417",
    "output": {
      "payload": {
        "currency": "USD",
        "kind": "scalar_observation",
        "unit": "million USD",
        "value": "819.2"
      },
      "selected_ref": "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
    }
  },
  "remaining_uncertainty_refs": [],
  "state_id": "finance_qa_vnext_state:dc3aa3dd7e0c980c89092e6965708111890d041767b19cff932591c6b7e73a37"
}
```

</details>


<details>
<summary>展开本次回执、观察及状态引用</summary>

```json
{
  "sequence": 10,
  "request_id": "finance_qa_vnext_request:d205dba8ecb883559461f0c2ef838f395541aaac22f3d7a9872ff48bccd77d9e",
  "submission": {
    "callback_binding": {
      "automatic_retries": 0,
      "host_semantic_field_fill": false,
      "id": "qa_vnext_model_execution_callback_binding:28b6bf92cda61d05426e665ae1679076194054197f39efde697ead110ef76e21",
      "implementation": {
        "class": "OnlineModelCallback",
        "method": "generate",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport",
        "source_byte_count": 30336,
        "source_relative_path": "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_model_execution/transport.py",
        "source_sha256": "d2b8f3bfc1dcc06fd8e97b87e3d6a438cb7953574876e563f00da3cd2c55bdd0"
      },
      "model_configuration_id": "qa_vnext_model_execution_transport_config:e6869eff1807bc19fc09aff494959508a3b0991169092fd8b2243590148fed9f",
      "model_fallbacks": 0,
      "model_origin_requires_attempt_response_evidence": true,
      "origin": "model",
      "schema_version": "qa_vnext_model_execution_callback_binding.v1",
      "sender_implementation": {
        "class": "HttpxSender",
        "httpx_version": "0.28.1",
        "method": "send",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport"
      },
      "session_id": "qa_vnext_task_panel_session:768b7d5de873286ced2f7dd5a751e26043dea4b51cfb42e4a30780b5fca22574",
      "transport_kind": "live_http"
    },
    "host_repairs": [],
    "id": "finance_qa_vnext_submission:f850b8e36fcaa15882b01c796f47dde4fd476b48e64bf417c783624b9b957fed",
    "raw_bytes": 1380,
    "raw_sha256": "be64c51ef69f95da4079a7105d4f2ecf85a387df0c29b13a62a4f2d988e65b99",
    "request_id": "finance_qa_vnext_request:d205dba8ecb883559461f0c2ef838f395541aaac22f3d7a9872ff48bccd77d9e",
    "schema_version": "finance_qa_vnext_submission.v2"
  },
  "receipt": {
    "admitted": true,
    "error_code": null,
    "id": "finance_qa_vnext_receipt:45b906a03f39902c0a92830c538c6af22a228b949e736206abcc34adfdc9f5fa",
    "no_host_semantic_repair": true,
    "request_id": "finance_qa_vnext_request:d205dba8ecb883559461f0c2ef838f395541aaac22f3d7a9872ff48bccd77d9e",
    "schema_version": "finance_qa_vnext_receipt.v2",
    "state_id": "finance_qa_vnext_state:dc3aa3dd7e0c980c89092e6965708111890d041767b19cff932591c6b7e73a37",
    "submission_id": "finance_qa_vnext_submission:f850b8e36fcaa15882b01c796f47dde4fd476b48e64bf417c783624b9b957fed"
  },
  "observation": null,
  "post_state_id": "finance_qa_vnext_state:3c8497e069bcd2816e16740d3113c8571914bf5319eb80be68b9b7b92f5cfe6b"
}
```

</details>


<a id="t12"></a>

### T12 — Action / 动作

准入。

模型请求操作：`growth`。


```json
[
  {
    "kind": "claim",
    "ref_id": "finance_qa_vnext_claim:c7460dbb8c8021d71e81b13e991a4c5c47d775369ff618577e993b5f0f8fe5bd",
    "role": "income_earlier_value",
    "selector": "payload.value"
  },
  {
    "kind": "claim",
    "ref_id": "finance_qa_vnext_claim:6e15b03b2ecaa1642b993e223c15faddaf4e90ab3d7ee35f9443b94fa38227d4",
    "role": "income_later_value",
    "selector": "payload.value"
  }
]
```

实际解析输入：


```json
[
  {
    "ref_id": "income_earlier_value",
    "value": "742"
  },
  {
    "ref_id": "income_later_value",
    "value": "819.2"
  }
]
```

实际执行输出：


```json
{
  "value": "10.40431266846361185983827493"
}
```

提交后实际反馈：


```json
{
  "admitted": true,
  "code": "pending_observation_requires_callback_update"
}
```


<details>
<summary>展开完整模型提交（parsed，保留全部字段）</summary>

```json
{
  "decision": {
    "basis": {
      "claim_refs": [
        "finance_qa_vnext_claim:6e15b03b2ecaa1642b993e223c15faddaf4e90ab3d7ee35f9443b94fa38227d4",
        "finance_qa_vnext_claim:c7460dbb8c8021d71e81b13e991a4c5c47d775369ff618577e993b5f0f8fe5bd"
      ],
      "evidence_refs": [
        "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
        "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
      ],
      "relation": "requires"
    },
    "candidate_action_ids": [
      "finance_qa_vnext_offered_action:ae0ff5f384954313671ab40b5d9ca7dcbc8a180752af1e1d03e83a3c44916b42"
    ],
    "expected_effect": {
      "establishes_obligation": "income_growth",
      "output_schema": "percentage"
    },
    "obligation_id": "income_growth",
    "selected_action_id": "finance_qa_vnext_offered_action:ae0ff5f384954313671ab40b5d9ca7dcbc8a180752af1e1d03e83a3c44916b42",
    "selection_rule": "dependency_ready",
    "subgoal": "derive_quantity",
    "unresolved_uncertainty_refs": []
  },
  "inputs": [
    {
      "kind": "claim",
      "ref_id": "finance_qa_vnext_claim:c7460dbb8c8021d71e81b13e991a4c5c47d775369ff618577e993b5f0f8fe5bd",
      "role": "income_earlier_value",
      "selector": "payload.value"
    },
    {
      "kind": "claim",
      "ref_id": "finance_qa_vnext_claim:6e15b03b2ecaa1642b993e223c15faddaf4e90ab3d7ee35f9443b94fa38227d4",
      "role": "income_later_value",
      "selector": "payload.value"
    }
  ],
  "kind": "action",
  "operation": "growth",
  "parameters": {},
  "state_id": "finance_qa_vnext_state:3c8497e069bcd2816e16740d3113c8571914bf5319eb80be68b9b7b92f5cfe6b"
}
```

</details>


<details>
<summary>展开本次回执、观察及状态引用</summary>

```json
{
  "sequence": 11,
  "request_id": "finance_qa_vnext_request:0f0650d4b2fae5981c5c3690932aea3791ef3715069093d0bf10e20878f48720",
  "submission": {
    "callback_binding": {
      "automatic_retries": 0,
      "host_semantic_field_fill": false,
      "id": "qa_vnext_model_execution_callback_binding:28b6bf92cda61d05426e665ae1679076194054197f39efde697ead110ef76e21",
      "implementation": {
        "class": "OnlineModelCallback",
        "method": "generate",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport",
        "source_byte_count": 30336,
        "source_relative_path": "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_model_execution/transport.py",
        "source_sha256": "d2b8f3bfc1dcc06fd8e97b87e3d6a438cb7953574876e563f00da3cd2c55bdd0"
      },
      "model_configuration_id": "qa_vnext_model_execution_transport_config:e6869eff1807bc19fc09aff494959508a3b0991169092fd8b2243590148fed9f",
      "model_fallbacks": 0,
      "model_origin_requires_attempt_response_evidence": true,
      "origin": "model",
      "schema_version": "qa_vnext_model_execution_callback_binding.v1",
      "sender_implementation": {
        "class": "HttpxSender",
        "httpx_version": "0.28.1",
        "method": "send",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport"
      },
      "session_id": "qa_vnext_task_panel_session:768b7d5de873286ced2f7dd5a751e26043dea4b51cfb42e4a30780b5fca22574",
      "transport_kind": "live_http"
    },
    "host_repairs": [],
    "id": "finance_qa_vnext_submission:a8a33e3c1d12b00cd11785daa3c96690ce0cf468ebb7d0049fb908940289780e",
    "raw_bytes": 1696,
    "raw_sha256": "92abc0d2a9daa23ae87f2cb5d64f7f9ef58a903e0c491063e29f7e10be47ab26",
    "request_id": "finance_qa_vnext_request:0f0650d4b2fae5981c5c3690932aea3791ef3715069093d0bf10e20878f48720",
    "schema_version": "finance_qa_vnext_submission.v2"
  },
  "receipt": {
    "admitted": true,
    "error_code": null,
    "id": "finance_qa_vnext_receipt:0f4c0311644b80d1fae9b974a597d44e09ca6cbb0548b79598ba85b5ac3ad33f",
    "no_host_semantic_repair": true,
    "request_id": "finance_qa_vnext_request:0f0650d4b2fae5981c5c3690932aea3791ef3715069093d0bf10e20878f48720",
    "schema_version": "finance_qa_vnext_receipt.v2",
    "state_id": "finance_qa_vnext_state:3c8497e069bcd2816e16740d3113c8571914bf5319eb80be68b9b7b92f5cfe6b",
    "submission_id": "finance_qa_vnext_submission:a8a33e3c1d12b00cd11785daa3c96690ce0cf468ebb7d0049fb908940289780e"
  },
  "observation": {
    "action_submission_id": "finance_qa_vnext_submission:a8a33e3c1d12b00cd11785daa3c96690ce0cf468ebb7d0049fb908940289780e",
    "execution_id": "finance_qa_vnext_execution:2a6151ed34d588b1b7d8bb6f5ebbb69b8284ce6562b5dd52ff3f928d53943145",
    "id": "finance_qa_vnext_observation:2af466a5e8d089738d067237523da187e6ff32df4ae6c7fbf2d878f0ca665d0b",
    "independent_output_valid": true,
    "obligation_id": "income_growth",
    "proposition": {
      "lineage": [
        "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
        "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
      ],
      "operation": "growth",
      "operation_contract_id": "operation_semantic_contract:01c784c5ca5f8800bfba52102d3c585fa040eb5b20a0529c7e0b8d303ebe9e5b",
      "output": {
        "value": "10.40431266846361185983827493"
      }
    },
    "receipt_id": "finance_qa_vnext_receipt:0f4c0311644b80d1fae9b974a597d44e09ca6cbb0548b79598ba85b5ac3ad33f",
    "schema_version": "finance_qa_vnext_observation.v2",
    "selected_action": {
      "alternative_group": "income_growth",
      "basis": {
        "claim_refs": [
          "finance_qa_vnext_claim:6e15b03b2ecaa1642b993e223c15faddaf4e90ab3d7ee35f9443b94fa38227d4",
          "finance_qa_vnext_claim:c7460dbb8c8021d71e81b13e991a4c5c47d775369ff618577e993b5f0f8fe5bd"
        ],
        "evidence_refs": [
          "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
          "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
        ],
        "relation": "requires"
      },
      "expected_effect": {
        "establishes_obligation": "income_growth",
        "output_schema": "percentage"
      },
      "id": "finance_qa_vnext_offered_action:ae0ff5f384954313671ab40b5d9ca7dcbc8a180752af1e1d03e83a3c44916b42",
      "input_order_policy": "ordered",
      "inputs": [
        {
          "kind": "claim",
          "ref_id": "finance_qa_vnext_claim:c7460dbb8c8021d71e81b13e991a4c5c47d775369ff618577e993b5f0f8fe5bd",
          "role": "income_earlier_value",
          "selector": "payload.value"
        },
        {
          "kind": "claim",
          "ref_id": "finance_qa_vnext_claim:6e15b03b2ecaa1642b993e223c15faddaf4e90ab3d7ee35f9443b94fa38227d4",
          "role": "income_later_value",
          "selector": "payload.value"
        }
      ],
      "obligation_id": "income_growth",
      "operation": "growth",
      "operation_contract_id": "operation_semantic_contract:01c784c5ca5f8800bfba52102d3c585fa040eb5b20a0529c7e0b8d303ebe9e5b",
      "parameters": {},
      "schema_version": "finance_qa_vnext_offered_action.v2",
      "selection_rules": [
        "dependency_ready",
        "registered_semantic_preconditions"
      ],
      "semantic_choice": [],
      "subgoal": "derive_quantity"
    }
  },
  "post_state_id": "finance_qa_vnext_state:b11ebd9cac11c74b446580c49be2b2a7dfdab947df9d0320d0da23bcf694ccb8"
}
```

</details>


<a id="t13"></a>

### T13 — Update / 接受或拒绝观察

准入。

模型处置：`accept`；后续子目标：`signed_gap`。

实际建立Claim：`finance_qa_vnext_claim:73f8a0d32e75e8991946a5e435abc7e00e98992724f1470cedcc7636deba1f37`。


```json
{
  "lineage": [
    "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
    "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
  ],
  "operation": "growth",
  "operation_contract_id": "operation_semantic_contract:01c784c5ca5f8800bfba52102d3c585fa040eb5b20a0529c7e0b8d303ebe9e5b",
  "output": {
    "value": "10.40431266846361185983827493"
  }
}
```

提交后实际反馈：


```json
{
  "admitted": true,
  "code": "claim_accepted"
}
```


<details>
<summary>展开完整模型提交（parsed，保留全部字段）</summary>

```json
{
  "assessment": {
    "evidence_refs": [
      "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
      "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
    ],
    "fulfills_obligation": "income_growth",
    "observation_refs": [
      "finance_qa_vnext_observation:2af466a5e8d089738d067237523da187e6ff32df4ae6c7fbf2d878f0ca665d0b"
    ],
    "relation": "accepts_observed_proposition"
  },
  "disposition": "accept",
  "kind": "update",
  "newly_enabled_obligation_ids": [
    "signed_gap"
  ],
  "next_subgoal": "signed_gap",
  "observation_id": "finance_qa_vnext_observation:2af466a5e8d089738d067237523da187e6ff32df4ae6c7fbf2d878f0ca665d0b",
  "proposed_claim": {
    "lineage": [
      "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
      "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
    ],
    "operation": "growth",
    "operation_contract_id": "operation_semantic_contract:01c784c5ca5f8800bfba52102d3c585fa040eb5b20a0529c7e0b8d303ebe9e5b",
    "output": {
      "value": "10.40431266846361185983827493"
    }
  },
  "remaining_uncertainty_refs": [],
  "state_id": "finance_qa_vnext_state:b11ebd9cac11c74b446580c49be2b2a7dfdab947df9d0320d0da23bcf694ccb8"
}
```

</details>


<details>
<summary>展开本次回执、观察及状态引用</summary>

```json
{
  "sequence": 12,
  "request_id": "finance_qa_vnext_request:4ed797368249caea69bd09bef440c9ade3405c020632e9122ead05a2c352fbea",
  "submission": {
    "callback_binding": {
      "automatic_retries": 0,
      "host_semantic_field_fill": false,
      "id": "qa_vnext_model_execution_callback_binding:28b6bf92cda61d05426e665ae1679076194054197f39efde697ead110ef76e21",
      "implementation": {
        "class": "OnlineModelCallback",
        "method": "generate",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport",
        "source_byte_count": 30336,
        "source_relative_path": "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_model_execution/transport.py",
        "source_sha256": "d2b8f3bfc1dcc06fd8e97b87e3d6a438cb7953574876e563f00da3cd2c55bdd0"
      },
      "model_configuration_id": "qa_vnext_model_execution_transport_config:e6869eff1807bc19fc09aff494959508a3b0991169092fd8b2243590148fed9f",
      "model_fallbacks": 0,
      "model_origin_requires_attempt_response_evidence": true,
      "origin": "model",
      "schema_version": "qa_vnext_model_execution_callback_binding.v1",
      "sender_implementation": {
        "class": "HttpxSender",
        "httpx_version": "0.28.1",
        "method": "send",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport"
      },
      "session_id": "qa_vnext_task_panel_session:768b7d5de873286ced2f7dd5a751e26043dea4b51cfb42e4a30780b5fca22574",
      "transport_kind": "live_http"
    },
    "host_repairs": [],
    "id": "finance_qa_vnext_submission:93bdc306c9b3f2da242543c9aff5bd7ca74ae6f55e73e62297a27417f05ea232",
    "raw_bytes": 1354,
    "raw_sha256": "9a4c1ef6af3fe816a53ecca5b1bbed8bae162a8a20f57ecd423be11e2ac25da8",
    "request_id": "finance_qa_vnext_request:4ed797368249caea69bd09bef440c9ade3405c020632e9122ead05a2c352fbea",
    "schema_version": "finance_qa_vnext_submission.v2"
  },
  "receipt": {
    "admitted": true,
    "error_code": null,
    "id": "finance_qa_vnext_receipt:c520aa5cb535ee12d6b1927265d90634fe31dd8088992c94578f1878ee687f92",
    "no_host_semantic_repair": true,
    "request_id": "finance_qa_vnext_request:4ed797368249caea69bd09bef440c9ade3405c020632e9122ead05a2c352fbea",
    "schema_version": "finance_qa_vnext_receipt.v2",
    "state_id": "finance_qa_vnext_state:b11ebd9cac11c74b446580c49be2b2a7dfdab947df9d0320d0da23bcf694ccb8",
    "submission_id": "finance_qa_vnext_submission:93bdc306c9b3f2da242543c9aff5bd7ca74ae6f55e73e62297a27417f05ea232"
  },
  "observation": null,
  "post_state_id": "finance_qa_vnext_state:b55f592b00b339d9e190fbdd3c91955f021fb2afdfc6df895ad87d6b3b19726b"
}
```

</details>


<a id="t14"></a>

### T14 — Action / 动作

准入。

模型请求操作：`signed_percentage_point_gap`。


```json
[
  {
    "kind": "claim",
    "ref_id": "finance_qa_vnext_claim:73f8a0d32e75e8991946a5e435abc7e00e98992724f1470cedcc7636deba1f37",
    "role": "income_growth",
    "selector": "value"
  },
  {
    "kind": "claim",
    "ref_id": "finance_qa_vnext_claim:8cfc88648e868e6fee287a8496cf04db79430e2d29f4f41a5f3ce0eb671c993d",
    "role": "revenue_growth",
    "selector": "value"
  }
]
```

实际解析输入：


```json
[
  {
    "ref_id": "income_growth",
    "value": "10.40431266846361185983827493"
  },
  {
    "ref_id": "revenue_growth",
    "value": "7.646646700593592892283292400"
  }
]
```

实际执行输出：


```json
{
  "unit": "percentage_points",
  "value": "-2.757665967870018967554982530"
}
```

提交后实际反馈：


```json
{
  "admitted": true,
  "code": "pending_observation_requires_callback_update"
}
```


<details>
<summary>展开完整模型提交（parsed，保留全部字段）</summary>

```json
{
  "decision": {
    "basis": {
      "claim_refs": [
        "finance_qa_vnext_claim:73f8a0d32e75e8991946a5e435abc7e00e98992724f1470cedcc7636deba1f37",
        "finance_qa_vnext_claim:8cfc88648e868e6fee287a8496cf04db79430e2d29f4f41a5f3ce0eb671c993d"
      ],
      "evidence_refs": [
        "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
        "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
        "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
        "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
      ],
      "relation": "requires"
    },
    "candidate_action_ids": [
      "finance_qa_vnext_offered_action:acd709e93c63e1d52bee3518b736b1485c9652c771b2ce0de0ac07992ec3cc1c"
    ],
    "expected_effect": {
      "establishes_obligation": "signed_gap",
      "output_schema": "scalar"
    },
    "obligation_id": "signed_gap",
    "selected_action_id": "finance_qa_vnext_offered_action:acd709e93c63e1d52bee3518b736b1485c9652c771b2ce0de0ac07992ec3cc1c",
    "selection_rule": "dependency_ready",
    "subgoal": "derive_quantity",
    "unresolved_uncertainty_refs": []
  },
  "inputs": [
    {
      "kind": "claim",
      "ref_id": "finance_qa_vnext_claim:73f8a0d32e75e8991946a5e435abc7e00e98992724f1470cedcc7636deba1f37",
      "role": "income_growth",
      "selector": "value"
    },
    {
      "kind": "claim",
      "ref_id": "finance_qa_vnext_claim:8cfc88648e868e6fee287a8496cf04db79430e2d29f4f41a5f3ce0eb671c993d",
      "role": "revenue_growth",
      "selector": "value"
    }
  ],
  "kind": "action",
  "operation": "signed_percentage_point_gap",
  "parameters": {},
  "state_id": "finance_qa_vnext_state:b55f592b00b339d9e190fbdd3c91955f021fb2afdfc6df895ad87d6b3b19726b"
}
```

</details>


<details>
<summary>展开本次回执、观察及状态引用</summary>

```json
{
  "sequence": 13,
  "request_id": "finance_qa_vnext_request:c647cc10d36c88289f103ca70c07f2bd3dbaca42f9df2835252f59034711b395",
  "submission": {
    "callback_binding": {
      "automatic_retries": 0,
      "host_semantic_field_fill": false,
      "id": "qa_vnext_model_execution_callback_binding:28b6bf92cda61d05426e665ae1679076194054197f39efde697ead110ef76e21",
      "implementation": {
        "class": "OnlineModelCallback",
        "method": "generate",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport",
        "source_byte_count": 30336,
        "source_relative_path": "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_model_execution/transport.py",
        "source_sha256": "d2b8f3bfc1dcc06fd8e97b87e3d6a438cb7953574876e563f00da3cd2c55bdd0"
      },
      "model_configuration_id": "qa_vnext_model_execution_transport_config:e6869eff1807bc19fc09aff494959508a3b0991169092fd8b2243590148fed9f",
      "model_fallbacks": 0,
      "model_origin_requires_attempt_response_evidence": true,
      "origin": "model",
      "schema_version": "qa_vnext_model_execution_callback_binding.v1",
      "sender_implementation": {
        "class": "HttpxSender",
        "httpx_version": "0.28.1",
        "method": "send",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport"
      },
      "session_id": "qa_vnext_task_panel_session:768b7d5de873286ced2f7dd5a751e26043dea4b51cfb42e4a30780b5fca22574",
      "transport_kind": "live_http"
    },
    "host_repairs": [],
    "id": "finance_qa_vnext_submission:ece6a683f6df1a6d5cbfc4de08fbc9cfa49524351c24af5a2c21c616077c93b0",
    "raw_bytes": 1888,
    "raw_sha256": "e82e42fed134015c1e53450ba59b2bd8b7c31b41239c12d95789d7958e8177f4",
    "request_id": "finance_qa_vnext_request:c647cc10d36c88289f103ca70c07f2bd3dbaca42f9df2835252f59034711b395",
    "schema_version": "finance_qa_vnext_submission.v2"
  },
  "receipt": {
    "admitted": true,
    "error_code": null,
    "id": "finance_qa_vnext_receipt:664822c0c621a9badccb08af077c5dc9212aa43a14bfef4a20f4edc8e7751f07",
    "no_host_semantic_repair": true,
    "request_id": "finance_qa_vnext_request:c647cc10d36c88289f103ca70c07f2bd3dbaca42f9df2835252f59034711b395",
    "schema_version": "finance_qa_vnext_receipt.v2",
    "state_id": "finance_qa_vnext_state:b55f592b00b339d9e190fbdd3c91955f021fb2afdfc6df895ad87d6b3b19726b",
    "submission_id": "finance_qa_vnext_submission:ece6a683f6df1a6d5cbfc4de08fbc9cfa49524351c24af5a2c21c616077c93b0"
  },
  "observation": {
    "action_submission_id": "finance_qa_vnext_submission:ece6a683f6df1a6d5cbfc4de08fbc9cfa49524351c24af5a2c21c616077c93b0",
    "execution_id": "finance_qa_vnext_execution:5040548b978ce3a2845286850a9d57e88ab5db2d32922bb68ed961dabdb985a2",
    "id": "finance_qa_vnext_observation:6e83059eb1ecd318e7e4ce94ed47522beda6d7e36adb2112c230266cf5087cd5",
    "independent_output_valid": true,
    "obligation_id": "signed_gap",
    "proposition": {
      "lineage": [
        "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
        "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
        "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
        "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
      ],
      "operation": "signed_percentage_point_gap",
      "operation_contract_id": "operation_semantic_contract:c90840b699e7301d1a1b9339fd8fb964ff40fbb8c1e129753b734c2df33cafc0",
      "output": {
        "unit": "percentage_points",
        "value": "-2.757665967870018967554982530"
      }
    },
    "receipt_id": "finance_qa_vnext_receipt:664822c0c621a9badccb08af077c5dc9212aa43a14bfef4a20f4edc8e7751f07",
    "schema_version": "finance_qa_vnext_observation.v2",
    "selected_action": {
      "alternative_group": "signed_gap",
      "basis": {
        "claim_refs": [
          "finance_qa_vnext_claim:73f8a0d32e75e8991946a5e435abc7e00e98992724f1470cedcc7636deba1f37",
          "finance_qa_vnext_claim:8cfc88648e868e6fee287a8496cf04db79430e2d29f4f41a5f3ce0eb671c993d"
        ],
        "evidence_refs": [
          "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
          "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
          "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
          "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
        ],
        "relation": "requires"
      },
      "expected_effect": {
        "establishes_obligation": "signed_gap",
        "output_schema": "scalar"
      },
      "id": "finance_qa_vnext_offered_action:acd709e93c63e1d52bee3518b736b1485c9652c771b2ce0de0ac07992ec3cc1c",
      "input_order_policy": "ordered",
      "inputs": [
        {
          "kind": "claim",
          "ref_id": "finance_qa_vnext_claim:73f8a0d32e75e8991946a5e435abc7e00e98992724f1470cedcc7636deba1f37",
          "role": "income_growth",
          "selector": "value"
        },
        {
          "kind": "claim",
          "ref_id": "finance_qa_vnext_claim:8cfc88648e868e6fee287a8496cf04db79430e2d29f4f41a5f3ce0eb671c993d",
          "role": "revenue_growth",
          "selector": "value"
        }
      ],
      "obligation_id": "signed_gap",
      "operation": "signed_percentage_point_gap",
      "operation_contract_id": "operation_semantic_contract:c90840b699e7301d1a1b9339fd8fb964ff40fbb8c1e129753b734c2df33cafc0",
      "parameters": {},
      "schema_version": "finance_qa_vnext_offered_action.v2",
      "selection_rules": [
        "dependency_ready",
        "registered_semantic_preconditions"
      ],
      "semantic_choice": [],
      "subgoal": "derive_quantity"
    }
  },
  "post_state_id": "finance_qa_vnext_state:cfb328ce9fc7d7e8c63e6390b11765047222bbb09632600ef13bcc5e572a1993"
}
```

</details>


<a id="t15"></a>

### T15 — Update / 接受或拒绝观察

准入。

模型处置：`accept`；后续子目标：`result`。

实际建立Claim：`finance_qa_vnext_claim:8f8e8a9169438c902dc2f91b61b5f26a165a27181f4364949fce11b2c2bf72a4`。


```json
{
  "lineage": [
    "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
    "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
    "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
    "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
  ],
  "operation": "signed_percentage_point_gap",
  "operation_contract_id": "operation_semantic_contract:c90840b699e7301d1a1b9339fd8fb964ff40fbb8c1e129753b734c2df33cafc0",
  "output": {
    "unit": "percentage_points",
    "value": "-2.757665967870018967554982530"
  }
}
```

提交后实际反馈：


```json
{
  "admitted": true,
  "code": "claim_accepted"
}
```


<details>
<summary>展开完整模型提交（parsed，保留全部字段）</summary>

```json
{
  "assessment": {
    "evidence_refs": [
      "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
      "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
      "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
      "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
    ],
    "fulfills_obligation": "signed_gap",
    "observation_refs": [
      "finance_qa_vnext_observation:6e83059eb1ecd318e7e4ce94ed47522beda6d7e36adb2112c230266cf5087cd5"
    ],
    "relation": "accepts_observed_proposition"
  },
  "disposition": "accept",
  "kind": "update",
  "newly_enabled_obligation_ids": [
    "result"
  ],
  "next_subgoal": "result",
  "observation_id": "finance_qa_vnext_observation:6e83059eb1ecd318e7e4ce94ed47522beda6d7e36adb2112c230266cf5087cd5",
  "proposed_claim": {
    "lineage": [
      "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
      "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
      "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
      "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
    ],
    "operation": "signed_percentage_point_gap",
    "operation_contract_id": "operation_semantic_contract:c90840b699e7301d1a1b9339fd8fb964ff40fbb8c1e129753b734c2df33cafc0",
    "output": {
      "unit": "percentage_points",
      "value": "-2.757665967870018967554982530"
    }
  },
  "remaining_uncertainty_refs": [],
  "state_id": "finance_qa_vnext_state:cfb328ce9fc7d7e8c63e6390b11765047222bbb09632600ef13bcc5e572a1993"
}
```

</details>


<details>
<summary>展开本次回执、观察及状态引用</summary>

```json
{
  "sequence": 14,
  "request_id": "finance_qa_vnext_request:01338a77868cf313ec630c3fdf03775c39249b0d24644716846a9788b08b0d35",
  "submission": {
    "callback_binding": {
      "automatic_retries": 0,
      "host_semantic_field_fill": false,
      "id": "qa_vnext_model_execution_callback_binding:28b6bf92cda61d05426e665ae1679076194054197f39efde697ead110ef76e21",
      "implementation": {
        "class": "OnlineModelCallback",
        "method": "generate",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport",
        "source_byte_count": 30336,
        "source_relative_path": "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_model_execution/transport.py",
        "source_sha256": "d2b8f3bfc1dcc06fd8e97b87e3d6a438cb7953574876e563f00da3cd2c55bdd0"
      },
      "model_configuration_id": "qa_vnext_model_execution_transport_config:e6869eff1807bc19fc09aff494959508a3b0991169092fd8b2243590148fed9f",
      "model_fallbacks": 0,
      "model_origin_requires_attempt_response_evidence": true,
      "origin": "model",
      "schema_version": "qa_vnext_model_execution_callback_binding.v1",
      "sender_implementation": {
        "class": "HttpxSender",
        "httpx_version": "0.28.1",
        "method": "send",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport"
      },
      "session_id": "qa_vnext_task_panel_session:768b7d5de873286ced2f7dd5a751e26043dea4b51cfb42e4a30780b5fca22574",
      "transport_kind": "live_http"
    },
    "host_repairs": [],
    "id": "finance_qa_vnext_submission:8735d0d11d441fa0e847c0b83e0a632f93d1cb6e280b1c0ee159485afc3c5775",
    "raw_bytes": 1808,
    "raw_sha256": "552cc2dff72bff4a85b84ed0d364c796c7f2e114c7e2a2c695c6cdb653eef769",
    "request_id": "finance_qa_vnext_request:01338a77868cf313ec630c3fdf03775c39249b0d24644716846a9788b08b0d35",
    "schema_version": "finance_qa_vnext_submission.v2"
  },
  "receipt": {
    "admitted": true,
    "error_code": null,
    "id": "finance_qa_vnext_receipt:eed3a364515129016c134e83a7455b4bf8dc34f4106bf79d1d5fa19e72818cf4",
    "no_host_semantic_repair": true,
    "request_id": "finance_qa_vnext_request:01338a77868cf313ec630c3fdf03775c39249b0d24644716846a9788b08b0d35",
    "schema_version": "finance_qa_vnext_receipt.v2",
    "state_id": "finance_qa_vnext_state:cfb328ce9fc7d7e8c63e6390b11765047222bbb09632600ef13bcc5e572a1993",
    "submission_id": "finance_qa_vnext_submission:8735d0d11d441fa0e847c0b83e0a632f93d1cb6e280b1c0ee159485afc3c5775"
  },
  "observation": null,
  "post_state_id": "finance_qa_vnext_state:ff8a805568346bd2f6bc58790f271ca4aeaf71d541939a12f04a1b9d294660fd"
}
```

</details>


<a id="t16"></a>

### T16 — Action / 动作

准入。

模型请求操作：`absolute_percentage_point_gap`。


```json
[
  {
    "kind": "claim",
    "ref_id": "finance_qa_vnext_claim:8f8e8a9169438c902dc2f91b61b5f26a165a27181f4364949fce11b2c2bf72a4",
    "role": "signed_gap",
    "selector": "value"
  }
]
```

实际解析输入：


```json
[
  {
    "ref_id": "signed_gap",
    "value": "-2.757665967870018967554982530"
  }
]
```

实际执行输出：


```json
{
  "unit": "percentage_points",
  "value": "2.757665967870018967554982530"
}
```

提交后实际反馈：


```json
{
  "admitted": true,
  "code": "pending_observation_requires_callback_update"
}
```


<details>
<summary>展开完整模型提交（parsed，保留全部字段）</summary>

```json
{
  "decision": {
    "basis": {
      "claim_refs": [
        "finance_qa_vnext_claim:8f8e8a9169438c902dc2f91b61b5f26a165a27181f4364949fce11b2c2bf72a4"
      ],
      "evidence_refs": [
        "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
        "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
        "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
        "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
      ],
      "relation": "requires"
    },
    "candidate_action_ids": [
      "finance_qa_vnext_offered_action:a7735bc6f35e3a83a59f3c042a442cf0822736865200337ab56ea81b16f8c6bb"
    ],
    "expected_effect": {
      "establishes_obligation": "result",
      "output_schema": "scalar"
    },
    "obligation_id": "result",
    "selected_action_id": "finance_qa_vnext_offered_action:a7735bc6f35e3a83a59f3c042a442cf0822736865200337ab56ea81b16f8c6bb",
    "selection_rule": "dependency_ready",
    "subgoal": "derive_quantity",
    "unresolved_uncertainty_refs": []
  },
  "inputs": [
    {
      "kind": "claim",
      "ref_id": "finance_qa_vnext_claim:8f8e8a9169438c902dc2f91b61b5f26a165a27181f4364949fce11b2c2bf72a4",
      "role": "signed_gap",
      "selector": "value"
    }
  ],
  "kind": "action",
  "operation": "absolute_percentage_point_gap",
  "parameters": {},
  "state_id": "finance_qa_vnext_state:ff8a805568346bd2f6bc58790f271ca4aeaf71d541939a12f04a1b9d294660fd"
}
```

</details>


<details>
<summary>展开本次回执、观察及状态引用</summary>

```json
{
  "sequence": 15,
  "request_id": "finance_qa_vnext_request:03dc16c6c5507691b5ba99696151c02b9f582449ef977c165134bca96fa26c7a",
  "submission": {
    "callback_binding": {
      "automatic_retries": 0,
      "host_semantic_field_fill": false,
      "id": "qa_vnext_model_execution_callback_binding:28b6bf92cda61d05426e665ae1679076194054197f39efde697ead110ef76e21",
      "implementation": {
        "class": "OnlineModelCallback",
        "method": "generate",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport",
        "source_byte_count": 30336,
        "source_relative_path": "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_model_execution/transport.py",
        "source_sha256": "d2b8f3bfc1dcc06fd8e97b87e3d6a438cb7953574876e563f00da3cd2c55bdd0"
      },
      "model_configuration_id": "qa_vnext_model_execution_transport_config:e6869eff1807bc19fc09aff494959508a3b0991169092fd8b2243590148fed9f",
      "model_fallbacks": 0,
      "model_origin_requires_attempt_response_evidence": true,
      "origin": "model",
      "schema_version": "qa_vnext_model_execution_callback_binding.v1",
      "sender_implementation": {
        "class": "HttpxSender",
        "httpx_version": "0.28.1",
        "method": "send",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport"
      },
      "session_id": "qa_vnext_task_panel_session:768b7d5de873286ced2f7dd5a751e26043dea4b51cfb42e4a30780b5fca22574",
      "transport_kind": "live_http"
    },
    "host_repairs": [],
    "id": "finance_qa_vnext_submission:d4217157179e5f82f424d02cb445ae2a0a6132bbc433d399126278aeefb1dde0",
    "raw_bytes": 1579,
    "raw_sha256": "1caebd89d422f76fa36cb14adad0f38f4ed7046542a3f514269c3ae0524e3920",
    "request_id": "finance_qa_vnext_request:03dc16c6c5507691b5ba99696151c02b9f582449ef977c165134bca96fa26c7a",
    "schema_version": "finance_qa_vnext_submission.v2"
  },
  "receipt": {
    "admitted": true,
    "error_code": null,
    "id": "finance_qa_vnext_receipt:8706134c1549a21ca53c09e16ef6836d74fc661367281099f22e0c218350dffa",
    "no_host_semantic_repair": true,
    "request_id": "finance_qa_vnext_request:03dc16c6c5507691b5ba99696151c02b9f582449ef977c165134bca96fa26c7a",
    "schema_version": "finance_qa_vnext_receipt.v2",
    "state_id": "finance_qa_vnext_state:ff8a805568346bd2f6bc58790f271ca4aeaf71d541939a12f04a1b9d294660fd",
    "submission_id": "finance_qa_vnext_submission:d4217157179e5f82f424d02cb445ae2a0a6132bbc433d399126278aeefb1dde0"
  },
  "observation": {
    "action_submission_id": "finance_qa_vnext_submission:d4217157179e5f82f424d02cb445ae2a0a6132bbc433d399126278aeefb1dde0",
    "execution_id": "finance_qa_vnext_execution:8931df5a1cc87502b1fed492ded697af1b3a9dca99b71fbe664927994c67a801",
    "id": "finance_qa_vnext_observation:58f6992616fabd02ce61b5b334287865d7e7eaf0442179939c4e14fcaa1568d5",
    "independent_output_valid": true,
    "obligation_id": "result",
    "proposition": {
      "lineage": [
        "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
        "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
        "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
        "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
      ],
      "operation": "absolute_percentage_point_gap",
      "operation_contract_id": "operation_semantic_contract:f4f57c892aca7e67b6ce371883449354996a18722bc1fdea52b4aa54d39a0900",
      "output": {
        "unit": "percentage_points",
        "value": "2.757665967870018967554982530"
      }
    },
    "receipt_id": "finance_qa_vnext_receipt:8706134c1549a21ca53c09e16ef6836d74fc661367281099f22e0c218350dffa",
    "schema_version": "finance_qa_vnext_observation.v2",
    "selected_action": {
      "alternative_group": "result",
      "basis": {
        "claim_refs": [
          "finance_qa_vnext_claim:8f8e8a9169438c902dc2f91b61b5f26a165a27181f4364949fce11b2c2bf72a4"
        ],
        "evidence_refs": [
          "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
          "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
          "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
          "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
        ],
        "relation": "requires"
      },
      "expected_effect": {
        "establishes_obligation": "result",
        "output_schema": "scalar"
      },
      "id": "finance_qa_vnext_offered_action:a7735bc6f35e3a83a59f3c042a442cf0822736865200337ab56ea81b16f8c6bb",
      "input_order_policy": "ordered",
      "inputs": [
        {
          "kind": "claim",
          "ref_id": "finance_qa_vnext_claim:8f8e8a9169438c902dc2f91b61b5f26a165a27181f4364949fce11b2c2bf72a4",
          "role": "signed_gap",
          "selector": "value"
        }
      ],
      "obligation_id": "result",
      "operation": "absolute_percentage_point_gap",
      "operation_contract_id": "operation_semantic_contract:f4f57c892aca7e67b6ce371883449354996a18722bc1fdea52b4aa54d39a0900",
      "parameters": {},
      "schema_version": "finance_qa_vnext_offered_action.v2",
      "selection_rules": [
        "dependency_ready",
        "registered_semantic_preconditions"
      ],
      "semantic_choice": [],
      "subgoal": "derive_quantity"
    }
  },
  "post_state_id": "finance_qa_vnext_state:d09eba79bfc97d148d0a7e238a46c6a7cd3becc73c2e91e4a01fe05ce567c393"
}
```

</details>


<a id="t17"></a>

### T17 — Update / 接受或拒绝观察

准入。

模型处置：`accept`；后续子目标：`submit_final`。

实际建立Claim：`finance_qa_vnext_claim:ba15bf9e93a7cf6fe796d10f82f6e4e2c7ee0dca63201b93f243e57e870d2c14`。


```json
{
  "lineage": [
    "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
    "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
    "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
    "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
  ],
  "operation": "absolute_percentage_point_gap",
  "operation_contract_id": "operation_semantic_contract:f4f57c892aca7e67b6ce371883449354996a18722bc1fdea52b4aa54d39a0900",
  "output": {
    "unit": "percentage_points",
    "value": "2.757665967870018967554982530"
  }
}
```

提交后实际反馈：


```json
{
  "admitted": true,
  "code": "claim_accepted"
}
```


<details>
<summary>展开完整模型提交（parsed，保留全部字段）</summary>

```json
{
  "assessment": {
    "evidence_refs": [
      "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
      "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
      "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
      "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
    ],
    "fulfills_obligation": "result",
    "observation_refs": [
      "finance_qa_vnext_observation:58f6992616fabd02ce61b5b334287865d7e7eaf0442179939c4e14fcaa1568d5"
    ],
    "relation": "accepts_observed_proposition"
  },
  "disposition": "accept",
  "kind": "update",
  "newly_enabled_obligation_ids": [],
  "next_subgoal": "submit_final",
  "observation_id": "finance_qa_vnext_observation:58f6992616fabd02ce61b5b334287865d7e7eaf0442179939c4e14fcaa1568d5",
  "proposed_claim": {
    "lineage": [
      "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
      "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
      "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
      "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
    ],
    "operation": "absolute_percentage_point_gap",
    "operation_contract_id": "operation_semantic_contract:f4f57c892aca7e67b6ce371883449354996a18722bc1fdea52b4aa54d39a0900",
    "output": {
      "unit": "percentage_points",
      "value": "2.757665967870018967554982530"
    }
  },
  "remaining_uncertainty_refs": [],
  "state_id": "finance_qa_vnext_state:d09eba79bfc97d148d0a7e238a46c6a7cd3becc73c2e91e4a01fe05ce567c393"
}
```

</details>


<details>
<summary>展开本次回执、观察及状态引用</summary>

```json
{
  "sequence": 16,
  "request_id": "finance_qa_vnext_request:8e4a4837d122dfa7d78c5cb6cb77478fc26ce63dc171914358780235f3c9a73e",
  "submission": {
    "callback_binding": {
      "automatic_retries": 0,
      "host_semantic_field_fill": false,
      "id": "qa_vnext_model_execution_callback_binding:28b6bf92cda61d05426e665ae1679076194054197f39efde697ead110ef76e21",
      "implementation": {
        "class": "OnlineModelCallback",
        "method": "generate",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport",
        "source_byte_count": 30336,
        "source_relative_path": "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_model_execution/transport.py",
        "source_sha256": "d2b8f3bfc1dcc06fd8e97b87e3d6a438cb7953574876e563f00da3cd2c55bdd0"
      },
      "model_configuration_id": "qa_vnext_model_execution_transport_config:e6869eff1807bc19fc09aff494959508a3b0991169092fd8b2243590148fed9f",
      "model_fallbacks": 0,
      "model_origin_requires_attempt_response_evidence": true,
      "origin": "model",
      "schema_version": "qa_vnext_model_execution_callback_binding.v1",
      "sender_implementation": {
        "class": "HttpxSender",
        "httpx_version": "0.28.1",
        "method": "send",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport"
      },
      "session_id": "qa_vnext_task_panel_session:768b7d5de873286ced2f7dd5a751e26043dea4b51cfb42e4a30780b5fca22574",
      "transport_kind": "live_http"
    },
    "host_repairs": [],
    "id": "finance_qa_vnext_submission:b13b6f2a9fa715e6414b31a1007c6ee6079e8689accc8590d886be6da2f5b1d1",
    "raw_bytes": 1795,
    "raw_sha256": "2e9b7a8c30f5d72c88ce69a5ed3a175ce063066e9937bfcc4644f91bef388485",
    "request_id": "finance_qa_vnext_request:8e4a4837d122dfa7d78c5cb6cb77478fc26ce63dc171914358780235f3c9a73e",
    "schema_version": "finance_qa_vnext_submission.v2"
  },
  "receipt": {
    "admitted": true,
    "error_code": null,
    "id": "finance_qa_vnext_receipt:e93a2cf0d214ad95c63a993e767343d1f6fa5dfb9974add13d6236f2385b6c27",
    "no_host_semantic_repair": true,
    "request_id": "finance_qa_vnext_request:8e4a4837d122dfa7d78c5cb6cb77478fc26ce63dc171914358780235f3c9a73e",
    "schema_version": "finance_qa_vnext_receipt.v2",
    "state_id": "finance_qa_vnext_state:d09eba79bfc97d148d0a7e238a46c6a7cd3becc73c2e91e4a01fe05ce567c393",
    "submission_id": "finance_qa_vnext_submission:b13b6f2a9fa715e6414b31a1007c6ee6079e8689accc8590d886be6da2f5b1d1"
  },
  "observation": null,
  "post_state_id": "finance_qa_vnext_state:d4a9278d456543a5fc18e1f889726d08ef6400cd24ca818e9079101eb964cfd6"
}
```

</details>


<a id="t18"></a>

### T18 — Final / 答案

准入。

本次提交的答案（是否被接受以上方回执为准）：


```json
{
  "unit": "percentage_points",
  "value": "2.757665967870018967554982530"
}
```

提交后实际反馈：


```json
{
  "admitted": true,
  "code": "complete"
}
```


<details>
<summary>展开完整模型提交（parsed，保留全部字段）</summary>

```json
{
  "answer_claim_id": "finance_qa_vnext_claim:ba15bf9e93a7cf6fe796d10f82f6e4e2c7ee0dca63201b93f243e57e870d2c14",
  "citations": [
    "evidence:finqa_archive_cell:20af3344a283d18bce2a746ae229a3d6858012f0872c6f92ff1b1139a5c26a43",
    "evidence:finqa_archive_cell:809dca76084da983b8f7f0f40865512eb49875cdb76603314e0ba370725315e2",
    "evidence:finqa_archive_cell:f790dc224358212537acab84aa0d0647bc8d26aa3952c9284cf22aad3370281e",
    "evidence:finqa_archive_cell:ffaccdc5c07a6b746edb92488f1eb1323ac7aab6380dd7f0c4cff079b7301773"
  ],
  "kind": "final",
  "result": {
    "unit": "percentage_points",
    "value": "2.757665967870018967554982530"
  },
  "state_id": "finance_qa_vnext_state:d4a9278d456543a5fc18e1f889726d08ef6400cd24ca818e9079101eb964cfd6"
}
```

</details>


<details>
<summary>展开本次回执、观察及状态引用</summary>

```json
{
  "sequence": 17,
  "request_id": "finance_qa_vnext_request:3799e107215cc45c83e3152db676de84194c90c82c82b60ec7843480638e39fd",
  "submission": {
    "callback_binding": {
      "automatic_retries": 0,
      "host_semantic_field_fill": false,
      "id": "qa_vnext_model_execution_callback_binding:28b6bf92cda61d05426e665ae1679076194054197f39efde697ead110ef76e21",
      "implementation": {
        "class": "OnlineModelCallback",
        "method": "generate",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport",
        "source_byte_count": 30336,
        "source_relative_path": "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_model_execution/transport.py",
        "source_sha256": "d2b8f3bfc1dcc06fd8e97b87e3d6a438cb7953574876e563f00da3cd2c55bdd0"
      },
      "model_configuration_id": "qa_vnext_model_execution_transport_config:e6869eff1807bc19fc09aff494959508a3b0991169092fd8b2243590148fed9f",
      "model_fallbacks": 0,
      "model_origin_requires_attempt_response_evidence": true,
      "origin": "model",
      "schema_version": "qa_vnext_model_execution_callback_binding.v1",
      "sender_implementation": {
        "class": "HttpxSender",
        "httpx_version": "0.28.1",
        "method": "send",
        "module": "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport"
      },
      "session_id": "qa_vnext_task_panel_session:768b7d5de873286ced2f7dd5a751e26043dea4b51cfb42e4a30780b5fca22574",
      "transport_kind": "live_http"
    },
    "host_repairs": [],
    "id": "finance_qa_vnext_submission:f75dbd4828d26e21736edb8e082355ef3be617a41e8a3637d016c9cccd3976ac",
    "raw_bytes": 756,
    "raw_sha256": "4d6ad86f48d4185c8c29e16b3a9530d835bdb474e799e2788c161caf74061407",
    "request_id": "finance_qa_vnext_request:3799e107215cc45c83e3152db676de84194c90c82c82b60ec7843480638e39fd",
    "schema_version": "finance_qa_vnext_submission.v2"
  },
  "receipt": {
    "admitted": true,
    "error_code": null,
    "id": "finance_qa_vnext_receipt:30afbe27f1438558b5a8ad0ecfb1edef08160a79a5fe949da48d1d3bb1c80369",
    "no_host_semantic_repair": true,
    "request_id": "finance_qa_vnext_request:3799e107215cc45c83e3152db676de84194c90c82c82b60ec7843480638e39fd",
    "schema_version": "finance_qa_vnext_receipt.v2",
    "state_id": "finance_qa_vnext_state:d4a9278d456543a5fc18e1f889726d08ef6400cd24ca818e9079101eb964cfd6",
    "submission_id": "finance_qa_vnext_submission:f75dbd4828d26e21736edb8e082355ef3be617a41e8a3637d016c9cccd3976ac"
  },
  "observation": null,
  "post_state_id": "finance_qa_vnext_state:94d685923edfbfea716065b21e66cdb8d24e87e476dc44e5e55ff8bc5dccde5e"
}
```

</details>


## 来源与审阅记录

来源实验：`qa_vnext_task_panel/fixed_eight_task_panel_v1_20260906`。

Session ID：`finance_qa_vnext_session:a91348ccdc9f729b2ce79800ac36dbbdba1ff5ed045a61f000224ed1adec7737`。

Qualification ID：`qa_vnext_model_execution_qualification:5943899a6abb3288b58aea4175e9462ca97c8990b1d1fc2972d9faff4a1cab30`。

本页为审阅视图；完整请求、候选与状态在[合格轨迹数据包](../trajectories.qualified.jsonl.gz)中。

人工审阅结论：待填写。

审阅备注：待填写。
