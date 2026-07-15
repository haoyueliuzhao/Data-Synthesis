# QA V4 Graph Pattern Compiler

## 目标

QA V4 将知识图谱从事后证据层推进为问题发现与推理规划层。新增链路是：

```text
KG motif discovery
→ Graph Pattern binding
→ executable Operation Plan
→ canonical semantics
→ deterministic question realization
→ independent plan replay
→ evidence and operation quality gates
→ split / benchmark / SFT / trace export
```

原有 Fact/DerivedFact QA 保持兼容；只有配置 `qa.graph_patterns.enabled=true` 时才追加图模式候选。

## 三个核心对象

### Graph Pattern

`qa_graph_patterns` 保存带版本的节点约束、边约束、语义约束、operator 模板、答案 schema 和基础难度。代码注册表位于 `finraw/qa/graph_patterns.py`。

当前可生成的模式：

- `pairwise_entity_metric_comparison`：两个实体、相同指标、相同期间；
- `entity_cross_metric_comparison`：同一实体、同一期间、两个可比指标；
- `entity_metric_temporal_average`：同一实体和指标的 3 至 5 个期间序列。

`entity_metric_time_lookup` 和 `fact_provenance_trace` 也已注册；前者对应现有 single-fact 结构，后者暂不启用，等待 evidence-trace 答案与文档证据扩展。

### Operation Plan

`qa_operation_plans` 独立保存：

```text
operator_dag
input_bindings
intermediate_results
output_schema
recompute_status
validation_errors
```

Operator Registry 当前提供 `lookup`、`difference`、`compare`、`mean`、`filter`、`rank`、`argmax` 和 `argmin`。每个 operator 检查输入结构、单位和币种，并返回结构化结果。复杂任务可以通过前一步输出引用构造 DAG，而不需要把每个组合预先物化成 DerivedFact。

### Question Realization

图模式先生成 `canonical_semantics`，再选择受控模板。新比较和时间聚合任务各有两个英文 surface forms，选择由稳定 candidate ID 决定，因此同一输入可复现。模板只接收实体、指标、时间和操作语义，不接收隐藏答案。

## 候选与样本字段

`qa_candidates` 新增：

```text
pattern_id
pattern_version
operation_plan_id
graph_features
difficulty_score
answer_schema
question_intent
```

`graph_features` 包括事实、派生事实、实体、指标、期间和来源数量，以及 evidence 节点/边、图跳数、分支数、操作数量、操作深度、scope 大小、时间跨度和答案基数。

`qa_samples` 新增：

```text
surface_form_id
paraphrase_group_id
linguistic_style
graph_pattern_id
operation_depth
```

## 质量门控

新图模式 QA 在原有事实、证据和答案检查之外，增加：

- `graph_pattern_match`：pattern bindings 与 candidate source facts 完全一致；
- `operator_input_complete`：所有绑定事实均属于固定 fact build；
- `operator_type_valid`：operator 输入类型、单位和币种兼容；
- `intermediate_result_recompute`：每个中间结果与重新执行结果一致；
- `operation_trace_coverage`：所有 source facts 均进入 operation trace；
- `independent_recompute`：最终答案与重新执行 Operation Plan 的结果一致。

Evidence Subgraph 仍要求每个 Fact 有 Entity、Metric、TimePeriod、DataSource 等关系，且整张证据子图连通。

## 难度与分析

难度由图特征和 operator 成本共同计算，分为 `easy`、`medium`、`hard`、`expert`、`research`。`multi_period_average` 进入 complex split，并继续采用 70/10/20 的 train/dev/test complex 分配。

运行分析：

```bash
python -m finraw.cli \
  --config config/profiles/prod_phase1_with_cninfo_generated.json \
  qa-analysis \
  --qa-build-id <qa_build_id> \
  --output-dir data/audit/qa_analysis
```

报告包含 graph-pattern/operation-plan 数量与熵、问题意图、答案类型、难度和 split 分布，以及 Fact/DerivedFact 节点利用率、edge type coverage 和 evidence 规模。

## V3 生产基线

对 `qa_build_20260712_023651_7adad081` 的审计结果：

- 68,231 candidates，64,221 eligible samples；
- graph pattern 和 operation plan 均为 legacy 单一类别，pattern entropy 为 0；
- Fact node utilization 为 39.55%；
- DerivedFact node utilization 为 27.17%；
- evidence 使用 11/22 种边，edge type coverage 为 50%；
- 最大单模板占比为 24.12%。

基线文件位于 `data/audit/qa_v4_baseline/`。

## 后续边界

本阶段完成了 V4 的基础编译框架和三个可靠 motif。下一阶段仍需在该框架上实现 `filter → ranking`、`argmax → cross-metric lookup`、`ranking → secondary metric`、历史 membership 和跨来源冲突路径，并增加 graph-pattern、operator-composition、metric-pair 和 scope holdout。
