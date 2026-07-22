# Financial Analysis Compiler

## 设计定位

Financial Analysis Compiler 是 QA V4 旁边的独立半开放分析主链。它复用 pinned KG、标准事实、语义口径、确定性算子和证据子图，但不把分析样本写入 `qa_samples`。

```text
                           +-> Closed-form QA Compiler
KG / graph-ready facts ----|
                           +-> Semi-open Financial Analysis Compiler
```

封闭 QA 验证唯一答案；半开放分析验证 Claim 是否由证据支持、结论是否属于合法集合、反向证据是否被处理。开放的是表达、组织顺序和分析侧重点，不是数字、实体、时间、因果或投资结论。

首版只支持描述、比较、诊断和风险信号总结。股票建议、目标价、预测、无证据因果解释和文档级管理层归因均被禁止。

## 主链

```text
quality-passed pinned KG
  -> graph-ready annual consolidated facts
  -> Analysis Pattern binding
  -> deterministic Financial Signal execution
  -> Evidence Bundle
  -> Claim Graph and predicate-filtered Valid Conclusion Set
  -> deterministic Claim Plan or bounded Claim-grounded LLM realization
  -> independent signal/claim/evidence/text/numeric verifier
  -> entity/scope connected-component holdout split
  -> benchmark / SFT / trace-seed export
```

默认模式仍采用确定性 Claim Plan。设置 `analysis.generation.mode=controlled_llm` 后，LLM 接收压缩后的 Signal payload、mandatory Claim、合法结论、caveat 和 Numeric Slot，并只返回 Claim 对齐文本、合法结论和 caveat。它不能新增 Claim ID、Evidence ID、数字槽位、实体、指标、期间、因果、预测或投资建议。返回的结构化 Contract 不是语义证据；最终 Verifier 会独立解析每个 Claim 和结论句的正负/风险立场，并重新检查数字与单位。

## 六个核心对象

### Financial Signal Spec

`financial_signal_specs` 固定输入角色、口径约束、Operation DAG、方向和强度策略。`signal_hash` 使 Registry 内容可版本审计。

### Financial Signal Instance

`financial_signal_instances` 保存一次确定性执行的输入事实、计算计划、中间结果、payload、方向、强度、支持/反向证据和重算状态。它是 Fact 与 Claim 之间的可复算中间层。

### Analysis Pattern

`analysis_patterns` 定义所需 Signal 角色、Evidence 约束、Claim schema、结论策略和禁止 Claim。MVP 注册三个 Pattern：

- `operating_trend_summary_v1`：收入、净利润、经营现金流三年趋势。
- `growth_quality_diagnosis_v1`：增长、利润现金背离、利润率与资产效率。
- `peer_positioning_v1`：完整同行范围内的收入增长、净利率与杠杆百分位。

### Evidence Bundle

`analysis_evidence_bundles` 同时保存 Fact、Signal、KG 节点/边、来源原始对象、支持证据、反向证据、覆盖率和连通分量。它不是简单 ID 列表，而是一次分析的固定证据边界。

### Claim Plan

`analysis_claim_plans` 将回答拆成最小可验证 Claim，保存 polarity、support/counter signal、qualifier、required/optional/forbidden、依赖和冲突关系。Claim Plan 同时固定 mandatory Claim 和不可越过的推理边界。

### Valid Conclusion Set

同一证据可以支持多个措辞或侧重点，但只允许选择 `valid_conclusion_set` 中的结论。required Claim 必须出现，forbidden Claim 不得出现；冲突型结论必须同时承认积极与反向证据。

## Signal Registry

当前 10 个 Signal Spec 为：

```text
revenue_growth
profit_growth
operating_cash_flow_growth
trend_consistency
earnings_cash_divergence
margin_change
asset_efficiency_change
peer_growth_percentile
peer_margin_percentile
peer_leverage_percentile
```

所有计算使用 Decimal，并固定输入 Fact ID。`earnings_cash_divergence` 只能支持利润与现金流走势背离及相应 caveat，不能推导舞弊、管理能力或未来业绩。

## Scope 设计

单公司 Pattern 只使用：

```text
company + consolidated_entity + annual FY + non-forecast + graph_ready
```

Peer Pattern 要求 5-30 家完整成员，不截断 top-N。SEC 公司通过 canonical entity 的 CIK 回溯 `sec_submissions_json.sic`，以 `SEC SIC major group` 形成可审计上层同行范围；缺少 SEC SIC 的非 SEC/测试数据才回退到 canonical industry。scope key 同时固定：

```text
scope type / scope id / fiscal year / source / unit / currency
```

每个成员必须拥有同年收入、净利润、总资产、总负债以及上一年收入，所有百分位均在完整 eligible EntitySet 上计算。构建器不会再依赖每个实体预先选中的“最长概念序列”决定同行资格，而是针对每个 scope/year 直接全量查询 pinned KG，按验证状态、置信度、报告日期和稳定 Fact ID 选择 canonical slot。

Candidate 与 Evidence Bundle 同时固定：

    peer_scope_type
    peer_scope_id
    expected_scope_entity_ids
    scope_membership_hash
    scope_eligibility_policy_hash
    peer_scope_contract

peer_scope_contract 还冻结年份、来源、单位、币种、每个指标的 SourceDefinition compatibility class，以及完整资格策略。它既是构建输入，也是可复算的版本审计对象。

## 独立验证

### Signal Gate

```text
signal_input_complete
analysis_signal_semantic_gate
analysis_scope_gate
analysis_period_gate
analysis_unit_currency_gate
signal_operator_recompute
signal_payload/direction/strength match
signal_hash_match
```

统一语义门控 fail-closed 检查 graph-ready、forecast、source、SourceDefinition、frequency、seasonal adjustment、vintage、单位、币种、period type、consolidated entity scope、连续期间和完整同行实体集合。未知 Semantic Operator 直接拒绝。Verifier 从 pinned Fact 独立重放门控与 Signal，不信任发现阶段或已保存结果。

对于 Peer Pattern，最终 Verifier 不以“各 Role 集合彼此相等”作为完整性证明，而是绕过 mining pool 和 fact_scan_limit，重新查询 pinned standardized_facts + KG Fact nodes + canonical_entities + SEC SIC。以下检查全部 fail-closed：

    peer_scope_contract
    peer_scope_policy_hash
    peer_scope_membership_hash
    peer_scope_recomputed_universe
    peer_scope_fact_representation

其中 Candidate、Bundle、contract 和每个 Signal Role 的实体集合都必须与独立重建的 eligible universe 完全相等。即使所有 Role 同时漏掉同一家公司，也不能通过。

### Evidence Gate

```text
bundle_fact_coverage
bundle_signal_coverage
bundle_scope_completeness
bundle_period_completeness
bundle_graph_connectivity
bundle_counter_evidence_coverage
```

### Claim 与结论 Gate

```text
claim_id_valid
claim_alignment_evidence_exact
mandatory_claim_coverage == 1.0
claim_semantic_frame_contract
claim_context_contract
unknown_entity_count == 0
unknown_metric_count == 0
unknown_period_count == 0
unknown_predicate_count == 0
unknown_numeric_slot_count == 0
forbidden_claim_extension_count == 0
caveat_id_exact_match
claim_graph_relations
selected_conclusion predicate satisfied
conclusion_semantic_frame_contract
analysis_text_render_contract
forbidden_claim_count == 0
required counterevidence grounded in an exact constraining frame
```

Claim Graph 包含一个综合 Claim：它依赖基础 Claim，风险 Claim 与综合 Claim 建立 `contradicts_claim_ids`。Valid Conclusion Set 由 Pattern 允许集合与当前 Claim 状态 Predicate 的交集产生，不再自动接受不符合当前证据的保守结论。

### Semantic Frame 与文本 Gate

Claim 和 Conclusion 的核心含义不再由关键词 Stance Parser 判断。Claim Planner 为每个对象生成固定结构：

```json
{
  "subject": "cash_quality",
  "predicate": "constrains",
  "object": "growth_quality",
  "qualifier": "risk_caveat"
}
```

LLM 必须逐字段复制 Frame，只能选择注册的 `surface_form_id`；最终句子由程序渲染。Verifier 从 Claim Graph 的 `claim_type / claim_role / claim_polarity` 独立重建 Frame，核对存储 Frame、Surface ID、渲染句子和完整 `analysis_text`。任何 `surface_text`、自由 sentence 字段、Frame 改写或额外尾句都会 fail-closed。关键词 Parser 仅保留为诊断工具，不参与 Claim 或 Conclusion 的接受决策。

每个 Claim 还固定保存 `allowed_entity_ids / allowed_metric_ids / allowed_periods / allowed_predicates / allowed_numeric_slot_ids / forbidden_claim_extensions`。Verifier 从 Claim 绑定的 Signal 独立重算允许集合，并要求 `required_entity_slots`、`required_period_slots`、存储白名单和生成对齐上下文完全一致。Surface Registry 本身属于 manifest，因此合法句式不能在不提升版本的情况下加入管理层判断或其他金融结论。Claim Plan 同时固定 `required_caveat_ids`，最终验证要求观测集合与必需集合严格相等，不接受额外或重复 Caveat。

每个 Signal 数值仍被编译为 `Numeric Slot(value, unit, tolerance, source_signal_id)`。文本中的数字必须精确映射到 Numeric Slot 或允许期间，并通过单位校验；样本保存的 Numeric Slot 还必须与 Rubric 中的固定 Contract 完全一致。Judge Model 只能评估自然度，不能替代这些硬门控。

## Rubric 与切分

Rubric 类型为 `claim_grounded_analysis`，评价事实准确性、mandatory Claim、结论一致性、反向证据、不确定性和表达。硬失败包括错误实体/期间、无证据数字、虚构因果、非法结论、遗漏强制反向证据和投资建议。

切分先把共享实体或完整 peer scope 的样本合并为连通分量，再整体分配。除 train/dev/test_standard 外支持 `test_entity_holdout`、`test_temporal_holdout`、`test_peer_scope_holdout`、`test_signal_composition_holdout` 和 `test_conflicting_evidence`。每次 build 输出 entity、peer scope、evidence window 和 semantic cluster 的跨 split 泄漏审计，任一连通分量不会被拆开。

## 输出格式

- Evidence-given benchmark：`instruction + evidence_bundle + claim_schema + rubric`。
- SFT：`instruction + evidence_summary + analysis_text + claim_alignment + conclusion_text + numeric_slots`。
- Trace seed：Pattern -> Binding -> Signal -> Evidence -> Claim Graph -> Conclusion -> Generation -> Response。
- Manifest：包含生成方式、API 成功率、fallback、token、时延和费用估算审计。

首版不提供 retrieval benchmark，也不消费 document candidate facts。

## API 生成与独立审计

封闭 QA 的 `question_generation.mode=controlled_llm` 只让模型选择 Sentence Plan 枚举；`variants=3` 表示一次请求最多返回三个候选 Plan，不会把一个 Candidate 扩成三条 QA。半开放分析使用独立的 `analysis.generation.mode=controlled_llm`：模型在固定 Claim Graph 中选择 Claim 顺序、合法结论和注册 Surface Form，金融 Predicate 与最终核心句子由程序控制。两种测试不可混称。

每个半开放请求写入 `analysis_llm_calls`，不保存 prompt、response 或 API key，只保存：

```text
provider / endpoint_host / requested and response model
request_hash / response_hash / response_id
attempt_index / is_final_attempt / validation_errors
http_status / http_success / json_valid / structured_response_valid
controlled_generation / latency_ms
prompt_tokens / completion_tokens / total_tokens / estimated_cost
fallback_reason / error_type
```

API 门控与样本 verifier 独立。即使 fallback 文本完全正确，只要 HTTP、结构化输出、受控生成或 fallback 比例不达标，build 仍为 `quality_failed`。默认阈值为 HTTP、结构化和受控生成成功率至少 98%，fallback 至多 2%。语义不合格响应最多进行一次有界修复；请求数、样本数、重试数和最终 fallback 数分别审计，默认重试率不得超过 5%。模型单价未配置时 `estimated_cost` 为 `null`，不会以零费用误导审计。

非秘密测试配置为 `config/profiles/prod_analysis_llm_150_test.json`，配额为三个 Pattern 各 50 条。凭据仅从 `DASHSCOPE_API_KEY` 环境变量读取；当前 profile 使用 DashScope OpenAI-compatible `/compatible-mode/v1/chat/completions` 和 `qwen-turbo`，并允许通过模型目录自动回退到可用的 Qwen 模型。该配置定义了正确的半开放测试，但只有实际运行后生成的 build report、`analysis_llm_calls` 和 export manifest 才能证明 150 次调用结果。

## 命令

```bash
python -m finraw.cli --config <config> build-analysis \
  --kg-build-id <quality-passed-kg-build> \
  --output-dir data/audit/analysis_build \
  --no-activate

python -m finraw.cli --config <config> validate-analysis \
  --analysis-build-id <analysis-build-id>

python -m finraw.cli --config <config> analysis-diversity \
  --analysis-build-id <analysis-build-id> \
  --output-dir data/audit/analysis_build

python -m finraw.cli --config <config> export-analysis-jsonl \
  --analysis-build-id <analysis-build-id> \
  --output-dir data/analysis_exports
```

只有 quality-passed build 可导出。`--no-activate` 用于生产预演，不替换活动版本。

## 生产 Smoke

以下记录是确定性 Analysis 主链 smoke，不是 LLM API 生产验证。

2026-07-18 在 KG `kg_20260711_062123_bc4b4394` 上完成非激活 smoke build `analysis_build_e7b50427d67ca3b53c570f70`：

```text
3 patterns x 5 samples = 15 candidates
65 signal instances
15/15 verifier passed
train/dev/test_standard = 11/2/2
largest pattern share = 1/3
signal composition entropy = 1.584963
```

三类 Pattern 均达到最低门槛，rejection count 为 0，build gate passed。该 build 保持非激活，未改变生产 KG 或 QA 指针。

Peer Scope v1 上线前的首轮 9 条预演由新 Verifier 发现三个同行范围不完整并拒绝：SIC 73 漏掉 CRM、SPGI、V，SIC 36 漏掉 MU。根因是构建器按最长 SourceDefinition 序列预选事实，而不是按目标年份重建资格。修复后构建器与 Verifier 均以 pinned KG 全量 scope policy 为依据，但二者分别执行。非激活 build analysis_build_25bb2c2f08f20089a22fe0e1 的结果为：

    3 patterns x 3 samples = 9 candidates
    36 signal instances
    9/9 verifier passed
    peer_scope_* failures = 0
    build gate passed

报告保存在 data/audit/analysis_peer_scope_v1_preflight_20260718_v2。该运行未调用 LLM，未激活 build，也未改变生产指针。

## 2026-07-18 API 验证

真实 150 条半开放运行完成 150/150 HTTP 和结构化响应，消耗 688,309 tokens；独立 verifier 拒绝两条将风险 Claim 写成正向支持的文本，因此该非激活 build 保持失败且不可导出。随后 v1 关键词极性门控被 Semantic Frame v1 取代：LLM 不再提交 Claim sentence，只复制 Frame 并选择 Surface Form；Verifier 独立重建并精确渲染。历史结果与新 Contract 的边界见 [analysis_api_test_20260718.md](analysis_api_test_20260718.md)。

## 后续边界

Claim-level LLM realization、Counterevidence Gate、Numeric Slot 和多类 holdout 已进入主链。仍待完成的是修复后新的全量发布运行，以及跨来源冲突协调、preference/verifier 负例、文档级 EvidenceChunk、事件解释和自主检索。
