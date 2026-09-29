# 既有审阅失败离线归因（零模型）

本报告不重判原轨迹、不更改任何旧标签，也未访问钱包或控制进程。

## production_snapshot

固定登记分母：13022；本次文件快照中真实模型返回：4676；无模型返回的网络 UNKNOWN：64。

这不是活跃目录的原子全局快照，晚于文件成员枚举的新结果不计入。

### 分类

- `annotation_internal_inconsistency`：2156
- `consistent_reviewer_invalid_claim`：1
- `consistent_reviewer_valid_label`：2418
- `network_unknown_no_model_response`：64
- `no_response_in_snapshot`：8282
- `structure_or_return_format_failure`：101

### Annotation 内部不一致的描述性归因

- `action_annotation_binding`：8
- `approved_fragment_missing_proposition_link`：12
- `graph_or_node_annotation_binding`：765
- `nonassertive_surface_rule_rejection`：895
- `other_annotation_internal_inconsistency`：83
- `reported_valid_vs_claim_annotation_inconsistency`：6
- `retraction_annotation_consistency`：5
- `target_coverage_or_mask_annotation`：364
- `term_or_proposition_annotation_binding`：18

一致 invalid 仅代表原审阅器作出否定标签。理由代码是否成立、原金融过程是否真正出错，本次均未独立核验。

invalid 的原注释字段分布：`{"without_annotated_critical_nonsupported_proposition": 1}`。没有列出否定关键命题，不证明轨迹有效；列出了也不自动证明原财务错误。

### 固定顺序案例

- `annotation_internal_inconsistency`，原 job 序号 1，`slot:0cf155907522c2e642d003dd3259a81eaeeb2e0a05e4e8452153e470b58979ea`，任务 `GIS/2008/page_83.pdf-1`，审阅侧 1。
  原检查错误：`nonassertive context requires explicit future opt-in and an empty optional Q field`。
  原模型理由代码：`["source_grounded_net_assets", "program_matches_gold", "action_observation_linked", "routine_submission_not_chi", "no_retraction", "no_critical_contradiction"]`。
  原返回：[record.json](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/conditional_five_arm_v9_01/jobs/slot_0cf155907522c2e642d003dd3259a81eaeeb2e0a05e4e8452153e470b58979ea/response/record.json)；SHA256 `91220129e278ba10e40c00446a2ca14a7fd4555495c7aa978643deb972e6aed2`。
  审阅输出引用并标记为 nonassertive、但超出原表面规则的片段：`R: The question asks for the change in net assets from 2007 to 2008. `（本次没有重新核对原 Episode，也未判定其应被豁免）。
  审阅输出引用并标记为 nonassertive、但超出原表面规则的片段：`This is a complete allowed operation matching the question's request.`（本次没有重新核对原 Episode，也未判定其应被豁免）。
- `annotation_internal_inconsistency`，原 job 序号 2，`slot:b97f478e6a49e7d9eb9d519a58edf7e0292441211fe68115ecd0214ce86548ed`，任务 `TSCO/2017/page_68.pdf-3`，审阅侧 0。
  原检查错误：`unbound semantic node`。
  原模型理由代码：`["all_critical_claims_supported", "no_retractions", "no_substantive_update", "routine_execution_then_submission", "native_answer_13_million_matches"]`。
  原返回：[record.json](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/conditional_five_arm_v9_01/jobs/slot_b97f478e6a49e7d9eb9d519a58edf7e0292441211fe68115ecd0214ce86548ed/response/record.json)；SHA256 `e09f97c3b1b6dd8928b84505509eda16550691f898080554f1a8a59dcd3c9d18`。
- `consistent_reviewer_invalid_claim`，原 job 序号 4647，`slot:92b62ea8d30c250cea6f0b697d3eec7fa90fe1351abd708a17ea82f28b9d2676`，任务 `INTC/2018/page_48.pdf-1`，审阅侧 1。
  原模型理由代码：`["period_misread_dec292018_vs_dec302017", "question_asks_as_of_dec302017_but_model_used_dec292018", "no_substantive_verification_or_revision", "routine_submission_not_chi"]`。
  原返回：[record.json](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/conditional_five_arm_v9_01/jobs/slot_92b62ea8d30c250cea6f0b697d3eec7fa90fe1351abd708a17ea82f28b9d2676/response/record.json)；SHA256 `9ed5aafbf972b6d60ad235a97cf3aba54a8aa6935168e8e7356399e8985b8448`。
- `network_unknown_no_model_response`，原 job 序号 29，`slot:b78fdd7babf88ddab1fabf6e09c86c94edc6ad82413ba4e83669d088e9802b90`，任务 `AES/2017/page_168.pdf-3`，审阅侧 1。
  原返回：[record.json](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/conditional_five_arm_v9_01/jobs/slot_b78fdd7babf88ddab1fabf6e09c86c94edc6ad82413ba4e83669d088e9802b90/response/record.json)；SHA256 `dd4e0e8468f5475a0e20aba647f9279b3dff5c330bc7d3d447ca67debf812a16`。
- `network_unknown_no_model_response`，原 job 序号 103，`slot:9a9bad94189379ab79acd85d89fd67dccca82c44b0c9cbdacd4d7dad8a7d66cc`，任务 `JPM/2017/page_144.pdf-4`，审阅侧 1。
  原返回：[record.json](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/conditional_five_arm_v9_01/jobs/slot_9a9bad94189379ab79acd85d89fd67dccca82c44b0c9cbdacd4d7dad8a7d66cc/response/record.json)；SHA256 `0a3513ab5e2a99fa1331ee330c125d5d0f1f56f1f2a2f4f2e39d52ccc79db15c`。
- `structure_or_return_format_failure`，原 job 序号 74，`slot:66757b15b187f7cfbca2e6d02444213473327a437d9a21870104d67d5d9ef5da`，任务 `NKE/2014/page_36.pdf-2`，审阅侧 0。
  原检查错误：`v8 interface JSONDecodeError: Extra data: line 1 column 6677 (char 6676)`。
  原返回：[record.json](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/conditional_five_arm_v9_01/jobs/slot_66757b15b187f7cfbca2e6d02444213473327a437d9a21870104d67d5d9ef5da/response/record.json)；SHA256 `01432fcef71eaa638b298d1c5bd3a56cc1d986944b5a1bf4248f9bbbf0c7de02`。
- `structure_or_return_format_failure`，原 job 序号 130，`slot:1bb7b5ecd5e8601fd0f726a432370c7b4836ee8a52e96740748bc3a2bc0b4d9b`，任务 `DISCA/2017/page_22.pdf-1`，审阅侧 0。
  原检查错误：`v8 interface JSONDecodeError: Expecting value: line 1 column 6435 (char 6434)`。
  原返回：[record.json](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/conditional_five_arm_v9_01/jobs/slot_1bb7b5ecd5e8601fd0f726a432370c7b4836ee8a52e96740748bc3a2bc0b4d9b/response/record.json)；SHA256 `b890fd5802e5885edd40dc752d670dcd5e09c3d393a267120ccba7a36e58ed47`。

## technical108

固定登记分母：108；本次文件快照中真实模型返回：108；无模型返回的网络 UNKNOWN：0。

这不是活跃目录的原子全局快照，晚于文件成员枚举的新结果不计入。

### 分类

- `annotation_internal_inconsistency`：70
- `consistent_alignment_annotation`：12
- `consistent_reviewer_invalid_claim`：5
- `consistent_reviewer_valid_label`：10
- `structure_or_return_format_failure`：11

### Annotation 内部不一致的描述性归因

- `approved_fragment_missing_proposition_link`：12
- `graph_or_node_annotation_binding`：10
- `nonassertive_surface_rule_rejection`：25
- `reported_valid_vs_claim_annotation_inconsistency`：1
- `target_coverage_or_mask_annotation`：15
- `term_or_proposition_annotation_binding`：7

一致 invalid 仅代表原审阅器作出否定标签。理由代码是否成立、原金融过程是否真正出错，本次均未独立核验。

invalid 的原注释字段分布：`{"without_annotated_critical_nonsupported_proposition": 5}`。没有列出否定关键命题，不证明轨迹有效；列出了也不自动证明原财务错误。

### 固定顺序案例

- `annotation_internal_inconsistency`，原 job 序号 0，`slot:af5c1580df3f52b17644d2620b5d075242037a10f4cd2dc7faa1db51443a05eb`，任务 `STZ/2010/page_51.pdf-3`，审阅侧 0。
  原检查错误：`nonassertive context requires explicit future opt-in and an empty optional Q field`。
  原模型理由代码：`["supported_key_facts", "action_grounded_derivation", "no_retraction", "no_critical_contradiction", "routine_submission_not_chi"]`。
  原返回：[record.json](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/audit_revision_20260929/review_validation_108_01/jobs/slot_af5c1580df3f52b17644d2620b5d075242037a10f4cd2dc7faa1db51443a05eb/response/record.json)；SHA256 `d6ad4b924fe32406a3d89cb1642f7dc9374ebd7843e3163f3ad28a75ff219c91`。
  审阅输出引用并标记为 nonassertive、但超出原表面规则的片段：`no further computation needed.

`（本次没有重新核对原 Episode，也未判定其应被豁免）。
- `annotation_internal_inconsistency`，原 job 序号 1，`slot:d9acbe0f18c6f421f91ba29455e5b619e705b5a1e89478d88d55dabd4f3d7715`，任务 `STZ/2010/page_51.pdf-3`，审阅侧 1。
  原检查错误：`nonassertive context requires explicit future opt-in and an empty optional Q field`。
  原模型理由代码：`["supported_critical_claims", "action_grounded", "consequential_verification", "no_retractions", "no_critical_contradiction"]`。
  原返回：[record.json](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/audit_revision_20260929/review_validation_108_01/jobs/slot_d9acbe0f18c6f421f91ba29455e5b619e705b5a1e89478d88d55dabd4f3d7715/response/record.json)；SHA256 `8a242a4d7c4a0421e3d29957a80d704428b417800bcbf854485222fc8795152f`。
  审阅输出引用并标记为 nonassertive、但超出原表面规则的片段：`I'll compute the comparison with a greater step after retrieving both figures.`（本次没有重新核对原 Episode，也未判定其应被豁免）。
  审阅输出引用并标记为 nonassertive、但超出原表面规则的片段：`no further computation needed.

`（本次没有重新核对原 Episode，也未判定其应被豁免）。
- `consistent_reviewer_invalid_claim`，原 job 序号 6，`slot:e1917f797e95aba06f09eff4f66035f9d40fbbb2646082c85cc2f7d40e25a5e8`，任务 `INTC/2018/page_105.pdf-2`，审阅侧 0。
  原模型理由代码：`["critical_contradiction_unretracted", "unsupported_key_claim", "v_trace_invalid", "native_answer_mismatch", "routine_verification_nonsubstantive"]`。
  原返回：[record.json](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/audit_revision_20260929/review_validation_108_01/jobs/slot_e1917f797e95aba06f09eff4f66035f9d40fbbb2646082c85cc2f7d40e25a5e8/response/record.json)；SHA256 `e7997846667d395bf44187e7bb96c089480306e1147c90cb9beaff702bcf917e`。
- `consistent_reviewer_invalid_claim`，原 job 序号 29，`slot:2b60f0c13d2236ea90943641508d1effcf0b872f80a2648817cad3b89dd16926`，任务 `TFX/2015/page_42.pdf-1`，审阅侧 1。
  原模型理由代码：`["native_answer_mismatch_1660000_vs_2660000", "critical_claim_unsupported_by_public_sources", "no_retraction_of_incorrect_total_return_interpretation", "routine_submission_not_substantive_verification"]`。
  原返回：[record.json](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/audit_revision_20260929/review_validation_108_01/jobs/slot_2b60f0c13d2236ea90943641508d1effcf0b872f80a2648817cad3b89dd16926/response/record.json)；SHA256 `530dec09173b2350dbe53feee3d9077593649710458bce1454928059f0df5e4e`。
- `structure_or_return_format_failure`，原 job 序号 3，`slot:f647571fa96a1137834313f07964df8ba14c8c8bf3267dc8b598867e06b70dfc`，任务 `MAS/2017/page_37.pdf-1`，审阅侧 1。
  原检查错误：`v8 interface JSONDecodeError: Expecting value: line 1 column 5267 (char 5266)`。
  原返回：[record.json](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/audit_revision_20260929/review_validation_108_01/jobs/slot_f647571fa96a1137834313f07964df8ba14c8c8bf3267dc8b598867e06b70dfc/response/record.json)；SHA256 `eb273009d78d4e51d3ccac9641d2398c7eee3441d3674df0b0a047b09434e72b`。
- `structure_or_return_format_failure`，原 job 序号 26，`slot:f8e986eea30e4d02a7b523575f94884de89c4e77b609d0aab9e3d40a6c72e474`，任务 `MAS/2017/page_37.pdf-1`，审阅侧 0。
  原检查错误：`v8 interface ValidationError: 1 validation error for SingleTargetOutput
propositions.3.judgment
  Field required [type=missing, input_value={'accepted': True, 'criti..._46', 'obs_0', 'obs_1']}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing`。
  原返回：[record.json](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/audit_revision_20260929/review_validation_108_01/jobs/slot_f8e986eea30e4d02a7b523575f94884de89c4e77b609d0aab9e3d40a6c72e474/response/record.json)；SHA256 `408dac6a8cd54268e6ac97b5c267374191173bb4bb0fd1874ece3188e4ea90e4`。

## 三个源码正则合成例证

以下不是原批模型输出；只复现未改动的有限表面规则，不计入真实失败频数。

- `I will inspect the public table.` → `ordinary_procedural_intent`
- `Let me inspect the public table.` → `None`
- `I will inspect the public table first.` → `None`

## 本次仍不可测

原8000条真实关键过程错误率、内部思维忠实性、审阅标签准确率、由schema造成的选择偏差大小、简化规则后的有效材料增量，均不能由本次统计确定。过程问题与annotation失败不得合并为金融错误率；技术批与生产批不拼成同一成绩总体。

本次只将已有记录按审计用途重新归类，不产生新的valid、不拓宽白名单、不提供训练准入。完整逐job绑定及短原返回引文见同目录JSON/JSONL。

## 描述性归因修订说明

初版将 retraction 中的 action 子串误归入动作标注类；本版仅将 action 匹配改为完整词，从初版已封存逐job摘要重算描述性family，不重读原API文件。原判定、主分类计数、例子选择和有效性均未改变。初版及完整逐job摘要永久保留，来源绑定见本版JSON。
