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
- `temporal_argmax_then_metric_lookup`：先在连续时间序列中寻找主指标峰值期间，再查询同一期间的第二指标。

三个单步模式的语义版本已提升到 v2。比较任务排除 forecast，并约束来源、来源定义、实体类型、scope、频率、时间口径、季调、vintage、单位和币种；跨指标任务还必须命中显式 Metric Pair Policy。时间任务仅使用同频、连续、定义一致的完整窗口。matcher 通过注册表绑定到 pattern，新增模式不再依赖 `if/elif` 分发。

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

Operator Registry 当前提供 `lookup`、`difference`、`compare`、`mean`、`filter`、`rank`、`argmax`、`argmin` 和 `select_by_period`。`temporal_argmax_then_metric_lookup` 实际执行 `argmax → select_by_period` 两步 DAG；主副序列在候选阶段固定，第二步按分析频率的 period index 对齐，验证时从 pinned facts 重放全部中间结果。

### Question Realization

图模式先生成 `canonical_semantics`，再选择受控模板。新比较和时间聚合任务各有两个英文 surface forms，选择由稳定 candidate ID 决定，因此同一输入可复现。模板只接收实体、指标、时间和操作语义，不接收隐藏答案。

## 候选与样本字段

`qa_candidates` 新增：

```text
pattern_id
pattern_version
pattern_hash
operation_plan_id
operation_plan_hash
graph_features
difficulty_score
answer_schema
question_intent
```

`graph_features` 包括事实、派生事实、实体、指标、期间和来源数量，以及 evidence 节点/边、图跳数、分支数、操作数量、操作深度、scope 大小、时间跨度和答案基数。
推理图深度与来源追溯深度分别记录为 `reasoning_graph_hop_depth` 和 `provenance_graph_depth`，避免 RawObject/SourceDefinition 叶节点抬高任务难度。

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
Build gate 还可要求每个 graph pattern 的最低正式样本数、最低 eligibility rate、最低 graph-feature coverage 和最低唯一 operator sequence 数。QA build 固定 `pattern_manifest_hash`、`operator_manifest_hash` 与 `difficulty_policy_hash`；已发布的 `pattern_id@version` 内容发生变化时会拒绝覆盖。

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

报告分别展示 `all_candidates`、`eligible_candidates`、`validated_samples` 和 `exported_samples` 四层漏斗，并区分 operator sequence、normalized plan hash 和完整 DAG hash。KG 利用率只以 eligible candidate 为口径。

正式构建前可运行只读预演：

```bash
python -m finraw.cli \
  --config config/profiles/prod_phase1_with_cninfo_generated.json \
  qa-pattern-preflight \
  --limit-per-pattern 500 \
  --output-dir data/audit/qa_pattern_preflight_v4
```

预演只发现和统计 motif，不创建 QA build。matcher 使用按指标分层的 indexed serving pool，再在内存中做确定性哈希 join/配对，避免在百万级 KG 边表上执行事实自连接。

## V3 生产基线

对 `qa_build_20260712_023651_7adad081` 的审计结果：

- 68,231 candidates，64,221 eligible samples；
- graph pattern 和 operation plan 均为 legacy 单一类别，pattern entropy 为 0；
- Fact node utilization 为 39.55%；
- DerivedFact node utilization 为 27.17%；
- evidence 使用 11/22 种边，edge type coverage 为 50%；
- 最大单模板占比为 24.12%。

基线文件位于 `data/audit/qa_v4_baseline/`。

## V4 正式库 Smoke 验证

最终 smoke build `qa_build_20260715_033418_a1af0f40` 固定到 KG `kg_20260711_062123_bc4b4394`，四种模式各构建 10 条：40/40 candidates eligible，40/40 samples 通过 Operation Plan 重放、evidence coverage 和独立复算。难度分布为：两类直接比较 `medium`，多期平均 `hard`，`argmax → lookup` 两步任务 `expert`。该 build 未执行 split，不会激活或替换生产 QA 版本。

## 后续边界

本阶段完成了 V4 编译框架、三个严格单步 motif 和首个真实两步 motif。下一阶段仍需实现 `filter → ranking`、`ranking → secondary metric`、cross-metric divergence、provenance trace、历史 membership 和跨来源冲突路径，并增加 graph-pattern、operator-composition、metric-pair 和 scope holdout。
