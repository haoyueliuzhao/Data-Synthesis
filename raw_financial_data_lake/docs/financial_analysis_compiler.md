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
  -> Claim Graph and Valid Conclusion Set
  -> deterministic evidence-given analysis text
  -> independent signal/claim/evidence/text verifier
  -> semantic-cluster split
  -> benchmark / SFT / trace-seed export
```

当前 MVP 采用确定性 Claim Plan 和文本实现，先验证数据模型与门控。后续 LLM 只能在 Claim Graph 内选择合法结论、可选 Claim、句序和风格；它不能产生新数字、新实体、新指标、新期间、新因果关系或投资建议。

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

每个成员必须拥有同年收入、净利润、总资产、总负债以及上一年收入，所有百分位均在完整 eligible EntitySet 上计算。

## 独立验证

### Signal Gate

```text
signal_input_complete
signal_operator_recompute
signal_payload/direction/strength match
signal_hash_match
```

Verifier 从 pinned Fact 重新执行 Signal，不信任已保存结果。

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
mandatory_claim_coverage == 1.0
selected_conclusion in valid_conclusion_set
forbidden_claim_count == 0
required counterevidence acknowledged
```

### 文本 Gate

文本中的数字必须映射到 Fact、Signal payload 或允许的期间；同时扫描错误实体、未知期间、预测词、因果词、推荐词和目标价表达。Judge Model 后续只能作为自然度软指标，不能替代硬门控。

## Rubric 与切分

Rubric 类型为 `claim_grounded_analysis`，评价事实准确性、mandatory Claim、结论一致性、反向证据、不确定性和表达。硬失败包括错误实体/期间、无证据数字、虚构因果、非法结论、遗漏强制反向证据和投资建议。

样本按 `analysis_semantic_cluster_id` 确定性切分为 70/10/20 的 train/dev/test_standard。同一 Evidence Bundle、Fact 组合和 Claim Plan 不跨 split。

## 输出格式

- Evidence-given benchmark：`instruction + evidence_bundle + claim_schema + rubric`。
- SFT：`instruction + evidence_summary + analysis_text + claim_alignment`。
- Trace seed：Pattern -> Binding -> Signal -> Evidence -> Claim -> Conclusion -> Response。

首版不提供 retrieval benchmark，也不消费 document candidate facts。

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

## 后续边界

P1 扩展 Claim-level LLM realization、Counterevidence Gate 和更完整的 holdout；P2 增加跨来源冲突协调及 preference/verifier 负例；文档级 EvidenceChunk、事件解释和自主检索留到文档证据链稳定之后。
