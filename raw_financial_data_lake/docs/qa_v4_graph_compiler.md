# QA V4 Graph Pattern Compiler

## 目标

QA V4 将知识图谱从事后证据层推进为问题发现与推理规划层。新增链路是：

```text
KG Pattern Mining
→ high-value Pattern Proposal
→ executable pattern binding
→ executable Operation Plan
→ canonical semantics
→ controlled template or LLM question realization
→ independent plan replay
→ evidence and operation quality gates
→ split / benchmark / SFT / trace export
```

原有 Fact/DerivedFact QA 保持兼容；只有配置 `qa.graph_patterns.enabled=true` 时才追加图模式候选。
原有 Fact/DerivedFact QA 保持兼容。人工注册 pattern 与自动挖掘 proposal 可以并行使用；自动 mining 不会把任意子图直接发布成 QA。

## KG Pattern Mining

`finraw/qa/pattern_mining.py` 从 pinned KG 对应的 graph-ready facts 建立受限 serving pool，自动统计四类可执行 motif：

- 同实体、同期间的可比指标共现；
- 同实体、同指标的连续时间序列；
- 同实体、同期间覆盖完整的双指标时间序列；
- 同行业、同期间、跨实体完整覆盖的双指标 scope。

系统自动发现具体的指标角色、来源口径、时间窗口、行业 scope 和可绑定事实，不再为每个指标组合编写 matcher。通用 motif grammar 仍由代码控制，这是有意保留的安全边界：KG 负责发现“哪些结构真实存在且覆盖充分”，operator registry 负责限制“哪些计算在金融语义上允许执行”。

每个 `qa_pattern_proposals` 记录：

```text
motif_signature / pattern_spec / operator_dag_template
binding_examples / support_count
support_score / completeness_score / financial_value_score
complexity_score / novelty_score / total_score
status / rejection_reasons / proposal_hash
```

只有支持度、绑定完整性和总评分均达标的 `approved` proposal 才能由 `pattern_compiler.py` 编译。QA candidate 同时固定 `mining_run_id`、`pattern_proposal_id`、`proposal_hash` 和 `pattern_score`，避免后续静默修改 proposal 语义。

运行顺序：

```bash
python -m finraw.cli --config <config> mine-qa-patterns \
  --kg-build-id <kg_build_id> \
  --output-dir data/audit/qa_pattern_mining

python -m finraw.cli --config <config> build-qa \
  --kg-build-id <kg_build_id> --no-activate
```

默认 `auto_run=false`，正式 QA build 消费该 KG 最近一次成功 mining run，便于先审计 proposal 再构建。开发环境可设 `auto_run=true` 进行端到端预演。

## 三个核心对象

### Graph Pattern

`qa_graph_patterns` 保存带版本的节点约束、边约束、语义约束、operator 模板、答案 schema 和基础难度。代码注册表位于 `finraw/qa/graph_patterns.py`。

当前可生成的模式：

- `pairwise_entity_metric_comparison`：两个实体、相同指标、相同期间；
- `entity_cross_metric_comparison`：同一实体、同一期间、两个可比指标；
- `entity_metric_temporal_average`：同一实体和指标的 3 至 5 个期间序列。
- `temporal_argmax_then_metric_lookup`：先在连续时间序列中寻找主指标峰值期间，再查询同一期间的第二指标。
- `industry_growth_filter_then_margin_rank`：在完整行业 scope 中计算收入增长，筛选后按净利率排名；
- `industry_revenue_rank_then_assets_lookup`：先按收入取 top-k，再连接同期间总资产；
- `industry_multi_factor_screening`：联合收入增长、行业平均净利率和负债率执行三条件筛选。

比较任务排除 forecast，并约束来源、来源定义、实体类型、scope、频率、时间口径、季调、vintage、单位和币种；跨指标任务还必须命中显式 Metric Pair Policy。时间任务仅使用同频、连续、定义一致的完整窗口。年度 flow 还必须覆盖 300 至 430 天，避免把 10-K 中的季度上下文误当作 FY。matcher 通过注册表绑定到 pattern，新增模式不再依赖 `if/elif` 分发。

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

Operator Registry 除基础查询、比较、均值、极值、筛选和排序外，还提供 `growth_by_entity`、`ratio_by_entity`、`intersect_on_entity`、`lookup_ranked_entities` 和 `multi_factor_screen`。复杂任务直接绑定底层标准事实，在计划内计算增长率和比率，不使用预先修正的 DerivedFact 答案。验证时从 pinned facts 重放全部中间结果。

### Question Realization

图模式先生成 `canonical_semantics`，再选择受控模板。`question_generation.mode=controlled_llm` 时，verbalizer 只向配置的 LLM 发送 canonical question、允许公开的语义和 immutable slots，绝不发送答案。LLM 输出必须通过 entity、metric、time、scope 和 operator slot round-trip；失败时自动回退到确定性模板。

默认模式是 `controlled_template`，因此离线构建完全可复现。启用 LLM 需要配置 endpoint、model 和 API key 环境变量；生成方式、slot 检查和 fallback 原因保存在 sample `source_metadata.question_generation` 中。

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
最终难度由 pattern base、推理图深度、operator 成本与深度、语义约束数量、scope 大小、时间跨度和 evidence 规模共同决定。

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
- `pattern_proposal_match`：proposal 必须 approved，hash/score/KG build 必须与 candidate 固定值一致；
- `question_slot_roundtrip`：问题保留全部不可变语义槽；
- `question_answer_isolation`：问题生成器未接收答案 payload。

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

正式构建前可运行不创建 QA 数据行的预演；命令会先执行幂等 schema 兼容检查：

```bash
python -m finraw.cli \
  --config config/profiles/prod_phase1_with_cninfo_generated.json \
  qa-pattern-preflight \
  --limit-per-pattern 500 \
  --output-dir data/audit/qa_pattern_preflight_v4
```

预演只发现和统计 motif，不创建 QA build。matcher 使用按指标分层的 indexed serving pool，再在内存中做确定性哈希 join/配对，避免在百万级 KG 边表上执行事实自连接。

需要执行完整 smoke build 时，应为 `build-qa` 增加 `--no-activate`。质量门控仍完整执行，但 passing build 保持非激活，不会替换当前生产 QA 指针。
自动 mining 的专用预演可使用 `build-qa --mined-only`；该模式在内存中关闭 legacy/static quotas，每个 proposal 默认只取一个 binding，并强制不激活，因此不需要复制生产连接配置。

## Pattern Mining 生产预演

对 KG `kg_20260711_062123_bc4b4394` 的最终 mining run `qamining_20260715_054441_65a5669e`：

- 扫描 70,605 个 graph-ready facts、24 个高覆盖指标；
- family-balanced 保留 100 个 proposal，88 个通过评分；
- approved 分布：cross-metric 25、scope rank follow-up 22、temporal aggregation 12、temporal extrema follow-up 29；
- rejected proposal 保留 rejection reasons，不进入 compiler。

mined-only smoke build `qa_build_20260715_055031_03f5d0ef` 从 88 个 approved proposals 各取一个 binding：88/88 candidates eligible，88/88 samples 通过 proposal hash、Operation DAG 中间结果、独立复算、evidence、question slot 和 split gate；build 保持非激活。难度分布为 medium 25、hard 12、expert 51，四种唯一 operator sequences，pattern entropy 6.459432。

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

## 第二阶段验证

生产预演在同一 KG 上发现：`filter → rank` 23 个、`rank → secondary lookup` 至少 100 个、multi-factor screening 32 个候选。最终 smoke build `qa_build_20260715_050301_b1f6fa4a` 三种模式各取 3 条，9/9 candidates eligible，9/9 samples 通过 evidence、逐步重放、表格答案复算和 split gate；该 build 保留为非激活审计记录。Fact-only evidence 不再扩展到引用这些事实的无关 DerivedFact，平均 evidence 节点由 89.33 降至 44.44。

标准事实增加 `entity_scope_id` 与 `financial_scope_type`。历史数据缺省解释为 canonical consolidated entity；未来 segment fact 必须提供独立 scope。时间和跨指标 join 要求 scope 完全一致，因此公司整体收入不能与地区或业务分部净利润拼接。

## 后续边界

自动 mining 当前采用“受控 motif grammar + KG 自动角色绑定”，不是无约束的通用子图枚举。下一阶段可加入 motif 频繁子图算法、指标本体关系学习和稳定的 node/edge constraint 到 SQL join plan 编译；在此之前，低价值或语义未知的任意子图不会进入 QA。其余重点是 provenance trace、历史 membership、跨来源冲突路径，以及 proposal、operator-composition、metric-pair 和 scope holdout。
