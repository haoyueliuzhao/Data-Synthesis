# QA V4 Graph Pattern Compiler

> Semi-open descriptive and diagnostic analysis is implemented as a sibling compiler rather than a QA subtype. It shares the pinned KG and verification infrastructure but persists Signals, Evidence Bundles, Claim Plans, and valid conclusion sets in separate analysis tables. See [Financial Analysis Compiler](financial_analysis_compiler.md).

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

原有 Fact/DerivedFact QA 保持兼容。人工注册 pattern 与自动挖掘 proposal 可以并行使用；自动 mining 不会把任意子图直接发布成 QA。

## KG Pattern Mining

`finraw/qa/pattern_mining.py` 从 pinned KG 对应的 graph-ready facts 建立受限 serving pool，自动统计四类可执行 motif：

- 同实体、同期间的可比指标共现；
- 同实体、同指标的连续时间序列；
- 同实体、同期间覆盖完整的双指标时间序列；
- 同行业、同期间、跨实体完整覆盖的双指标 scope。

系统自动发现具体的指标角色、来源口径、时间窗口、行业 scope 和可绑定事实，不再为每个指标组合编写 matcher。通用 motif grammar 仍由代码控制，这是有意保留的安全边界：KG 负责发现“哪些结构真实存在且覆盖充分”，operator registry 负责限制“哪些计算在金融语义上允许执行”。

Mining Pool 不再简单选择事实数最多的指标和排序前部记录。指标层在“业务价值清单”和“高支持度指标”之间分配 quota，并按 metric category、statement type 和 density bucket 轮转；事实层按 source、industry、entity type、year bucket、frequency 和 density bucket 分层采样。默认先扫描完整候选再确定性采样，`pool_scan_rows_per_metric` 仅作为显式资源上限。

每个 proposal 同时具有两个身份：

```text
proposal_semantic_id
只由规范化 motif grammar、metric roles、semantic constraints、operator DAG 和 answer schema 决定

proposal_snapshot_id
由 semantic ID、KG build、支持度、binding 样例和验证结果共同决定
```

同一语义模式可以跨 Mining Run 和 KG build 跟踪支持度变化，而不同快照不会覆盖。只有 proposal 与静态 registry 的规范化节点/边 grammar、task subtype、完整 operator DAG、全部 semantic constraints 和完整 answer schema 逐项相等，`static_pattern_overlap == 1.0` 且双方 `pattern_semantic_digest` 相等时，proposal 才标记为 `known_pattern_binding`。candidate 层再按事实集合、操作 DAG、时间、实体、指标和答案 schema 去重，避免静态与自动路径重复导出同一任务。

Mining 2.2.0 继续把五类 topology 记录到 `qa_graph_motif_observations`，但 observation 不再是四类高价值路径的终点。`derived_fact_composition / fact_provenance / time_hierarchy / entity_set_scope` 在有支持度且被 policy 启用时，会生成声明式 Pattern Spec，经同一 compiler、semantic gate、Operation DAG gate、held-out 与 Proposal 生命周期验证后写入 `qa_pattern_proposals`。`cross_source_reconciliation` 因当前 KG 无稳定支持且仍需冲突语义规则，继续保持 observation-only。Observation 的 `observed` 状态本身不授予发布资格。

每个 `qa_pattern_proposals` 记录：

```text
motif_signature / pattern_spec / operator_dag_template
binding_examples / heldout_bindings / support_count
support_score / completeness_score / financial_value_score
complexity_score / novelty_score / total_score
semantic_constraint_pass_rate / operation_execution_pass_rate
example_binding_pass_rate / heldout_binding_pass_rate
pattern_semantic_digest / static_pattern_overlap / binding_diversity_score
static_pattern_id / static_pattern_version / static_pattern_hash
manual_review_status / lifecycle_events / status
rejection_reasons / proposal_hash
```

Proposal 的成功路径为 `proposed → semantic_validated → execution_validated → reviewed_approved → published`；人工拒绝则从 `execution_validated` 进入明确终态 `reviewed_rejected`，不会继续停留在待审核状态。评分只负责排序，不能授予发布资格。所有保存的 binding examples 必须 100% 执行成功，额外的确定性 held-out bindings 必须达到至少 99% 执行通过率；当 `require_manual_review=true` 时，proposal 会停在 `execution_validated`，直到 `review_pattern_proposal()` 记录审核决定。只有 `published` proposal 才能由 `pattern_compiler.py` 编译并进入正式 QA build。

Example 与 held-out 按 binding 内容哈希确定性切分，二者互斥；held-out 不参与 candidate 生成。挖掘阶段使用与正式 QA 相同的 `materialize_plan()` 和 `execute_plan()` 逐条重放 Operation DAG，并持久化错误、输出 hash 和两组通过率。`static_pattern_overlap` 是节点 grammar、边 grammar、task subtype、规范化 operator DAG、semantic constraints 与完整 answer schema 六部分的诊断分数；只有六部分全部相等且规范化 SHA-256 摘要相等时才允许静态复用。其余 proposal 一律作为 `new_pattern`，`novelty_score` 取 overlap 的补集；`binding_diversity_score` 衡量实体、期间与 scope 的真实变化。

`semantic_constraints` 不是说明性标签。`semantic_constraints.py` 在三个阶段执行同一验证函数：mining binding 在计入 support 前校验，candidate 在进入 eligible pool 前复验，最终 verifier 再从 pinned facts 与持久化 pattern spec 独立执行。门控覆盖 registered comparable/follow-up metric pair、statement/period type、来源定义兼容类、financial scope、frequency、seasonal adjustment、vintage、forecast 与 graph-ready 状态。每个 check 保存 observed/expected，失败使用稳定的 `semantic_constraint:<check_name>` 原因码；proposal 另存 evaluated、accepted 和 rejection-count 诊断。

QA generator 4.5.0 / mining 1.7.0 将该契约收敛为 fail-closed 的 Semantic Operator Registry。当前注册并执行 `eq / ne / gte / gt / lt / same / compatible / compatible_by_series / contiguous / between_days / consolidated_entity / complete_across_bindings / same_within_binding / unique / registered metric pair / gt_industry_average`。其中 count、时间连续性、左右实体不等、主副序列 period coverage、scope 实体集合等值、行业一致、策略阈值和年度 duration 都由 verifier 根据 pinned facts 独立重算，不依赖 matcher 的发现结果。Pattern 声明未注册的 operator，或 operator 不支持的 field，都会在 Proposal、Candidate 和最终 QA 三个阶段直接失败，不能再委托给 specialized matcher 静默放行。

Semantic Operator Registry 1.1.0 将非空要求下沉到所有 Pattern 共用的 baseline admission gate。`source_id / time_basis / frequency / seasonal_adjustment / vintage_policy` 的兼容类必须存在且唯一，全空值不再被“相同”误放行。只有 Pattern 对对应 `same` 约束显式声明 `allow_missing=true` 时，baseline 与正式 operator 才会共同允许空值；缺少声明默认 fail-closed。年度财报可确定性推断出的 `seasonal_adjustment=not_applicable` 属于有效语义值，不按缺失处理。

最终 verifier 会从持久化 candidate 与 Operation DAG 恢复 `entity_ids`、`scope_definition`、`financial_scope` 和逐 step 参数，再执行同一注册表。因此自定义增长/负债阈值、完整 scope universe 和 follow-up coverage 不会在 candidate 持久化后丢失。实体的 industry、country、market 与 entity type 则从 pinned canonical entity build 重新加载；同数量但替换实体、不连续窗口、缺少副指标期间和被篡改阈值都会触发 `semantic_constraint_gate`。

季调口径采用显式优先的语义归一化：原始事实已有 `seasonal_adjustment` 时必须严格一致；年度序列以及指标本体明确标为财务报表的事实，其空值可确定性解释为 `not_applicable`；其他月频、季频宏观事实缺少季调信息时仍 fail-closed。该规则兼容历史 SEC filing facts，同时不会把高频宏观数据的未知季调口径当作可比。

时间窗口还采用前置口径隔离。`TemporalSeriesKey` 由 entity、metric、source、source definition、frequency、time basis、metric period type、financial scope、unit、currency、seasonal adjustment、vintage policy 和 comparability level 共同组成；任一字段变化都会先拆成独立 series，再分别执行连续窗口检测。同一指标存在多个完整定义版本时，各版本作为稳定排序的 series variant 独立参与匹配，不会按事实遍历顺序覆盖，也不会跨版本拼接年份。

自动 scope mining 使用同样严格的前置隔离。Scope context 固定 canonical industry、同期间、同来源、annual FY、consolidated entity、季调、vintage 和 comparability level；每个 metric variant 再固定 source definition、period type、unit 和 currency。每个实体在 primary/secondary 集合中必须各有且仅有一个事实，两个集合的 entity universe 必须完全一致。segment、forecast、非 FY、无效年度 duration、entity scope 错位和重复事实不会进入 proposal。`lookup_ranked_entities` 也会在输出单位前校验全部 secondary facts，不能以第一个事实掩盖混合单位或币种。

运行顺序：

```bash
python -m finraw.cli --config <config> mine-qa-patterns \
  --kg-build-id <kg_build_id> \
  --output-dir data/audit/qa_pattern_mining

python -m finraw.cli --config <config> transition-qa-mining-run \
  --mining-run-id <mining_run_id> \
  --target-status reviewed \
  --reviewer <reviewer>

python -m finraw.cli --config <config> transition-qa-mining-run \
  --mining-run-id <mining_run_id> \
  --target-status approved_for_qa \
  --reviewer <approver>

python -m finraw.cli --config <config> build-qa \
  --kg-build-id <kg_build_id> \
  --mining-run-id <mining_run_id> \
  --no-activate
```

Mining Run 采用 `running → success → reviewed → approved_for_qa → superseded` 生命周期；失败任务进入 `failed`。Mining 2.0.0 不再在 mining 完成时定稿 `approved_count`：每次 Proposal 人工审核后会刷新计数，进入 `reviewed` 时再次重算，进入 `approved_for_qa` 前执行权威 Proposal 状态与通过率审计。

Run 审批要求至少一个 `published` Proposal，且不得存在 `execution_validated` 或 `reviewed_approved` 等 unresolved 状态。带 rejection reason 的自动门控失败和 `reviewed_rejected` 是已解决拒绝项；后者必须同时具有 `manual_review_status=rejected` 与 `manual_review_rejected` 原因。所有 published Proposal 必须重新满足 semantic、operation、saved-example 和 held-out pass-rate 门槛。

审批通过时，系统冻结 `published_proposal_manifest` 及其 SHA-256 hash。manifest 固定 Proposal hash、semantic/snapshot ID、静态 Pattern pin、binding mode、支持度和四项通过率；`get_approved_mining_run()` 与正式 QA loader 每次使用前都会重新计算并比较 manifest、hash 和 `approved_count`。审批后 Proposal 内容发生变化将直接拒绝加载。历史 approved Run 缺少冻结 manifest 时不会自动回填，必须显式重新审核或迁移。

Mining 2.1.0 将 `reviewed → approved_for_qa` 与旧 Run supersede 放在同一个数据库事务中。SQLite 使用 `BEGIN IMMEDIATE`；PostgreSQL 在事务内按稳定顺序对目标 KG 的全部 Run 执行 `SELECT ... FOR UPDATE`，再重读状态并完成切换。数据库还通过部分唯一索引 `uq_one_approved_mining_run_per_kg` 保证每个 KG 最多一个 `approved_for_qa` Run；中途失败会整体 rollback，并发审批最终由行锁串行化、唯一索引兜底。迁移既有 PostgreSQL 数据库前必须先消解同一 KG 下的重复 approved Run，否则唯一索引创建会按预期失败。

`qa_builds.mining_run_id`、build notes 中的 selected run、proposal manifest 和 candidate 级 proposal/binding ID 共同形成审计边界。Proposal ID 以 Mining Run 为作用域，`proposal_hash` 保持内容身份，因此重复 mining 不会覆盖历史 run 的 Proposal。开发环境可同时设置 `auto_run=true` 与 `auto_approve_for_qa=true` 做端到端预演；默认 `auto_approve_for_qa=false`，正式配置不得用它替代审核。

## Pattern Compiler V2.4

Proposal 的审计样例与正式 QA 输入已经分离，且 binding discovery 现在由声明式 IR 执行：

```text
published Pattern Proposal.pattern_spec.binding_query
→ scan_pinned_fact_nodes
→ join_entity_metric_period
→ group / group_series
→ join_metric_roles / join_series_on_period / complete_case_metric_join
→ semantic_constraint_gate
→ operation_execution_gate
→ sample(method=deterministic_hash_stratified)
→ qa_compiled_bindings
→ QA candidate
```

mining 2.2.0 在每个 Pattern Spec 中持久化 `binding_query.ir_version / scan_kind / relational_ops / stratum_fields`，并为所有 Proposal 固定 `pattern_semantic_digest`。Compiler 2.6.0 不读取 `motif_family` 决定执行路径：fact plan 从 `scan_pinned_fact_nodes → join_entity_metric_period` 开始，graph plan 从 `scan_pinned_graph_nodes` 开始；两者都只解释 Proposal 声明的 operator，并统一追加 semantic、operation 和 sample gate，最终形成 `LogicalPatternPlan(plan_version=2, ir_version=1)`。没有 `binding_query` 的历史 proposal 只在编译期按 Operation DAG signature 迁移一次，不进入运行时 family dispatch。

静态复用是内容寻址的快照绑定。Proposal 必须同时固定 `static_pattern_id / static_pattern_version / static_pattern_hash`；compiler 会重新计算 Proposal spec 的语义摘要和当前 registry 的语义摘要、版本及完整内容 hash，任一项变化即拒绝编译。历史静态 Proposal 缺少这些 pin 时不会自动读取活动版本，必须重新 mining 或执行显式数据迁移。

`binding_executor.py` 使用统一 relation state 顺序解释 IR。事实侧支持 `scan_pinned_fact_nodes / group / join_metric_roles / group_series / join_series_on_period / complete_case_metric_join`；图侧支持通用的 `scan_pinned_graph_nodes / expand_graph_edges / project_graph_binding`。图 operator 的 root role、node type、边方向、relation、目标类型、one/collect 基数、最大关联节点数、答案字段投影与 sampling strata 全部来自 Pattern Spec。四类 graph-native task 只声明这些组合，没有新增 family dispatcher。`semantic_constraint_gate`、Operation DAG gate 与 `sample` 在同一 interpreter 链内执行，`sampling_summary.operator_trace` 保存每步 relation kind 和行数。

新增 motif family 只需声明已有 operator 的组合；executor 不读取 `motif_family` 决定执行路径。编译记录的 `sampling_summary.operator_trace` 保存每个 operator 的 position、input/output relation kind 和行数，可验证 `relational_ops` 确实被执行。`compiled_scan_rows_per_metric=0` 表示全量扫描，只有显式正数才施加运维上限；审计样例 hash 仅用于 overlap 统计和优先选择非样例 binding，不作为查询输入。

Graph-native 根节点目录扫描与昂贵的 binding 评估分别设置预算。`compiled_graph_scan_rows=0` 表示完整遍历根节点目录，不生成前部截断；`compiled_graph_evaluation_rows=0` 表示对全部已扫描根执行边展开、语义门控和 Operation DAG，正数则在完整目录扫描后按 node type、source、entity type、五年 year bucket 和 relation-density bucket 做确定性 hash 分层抽样。每个 compilation 同时保存 `total_root_count / scanned_root_count / root_coverage_rate` 与 `evaluated_root_count / evaluation_coverage_rate`，不能用 100% 的目录扫描覆盖率冒充 100% 的 binding 执行覆盖率。

单次 QA build 现在创建一个 build-scoped `MetricFactCache`，供全部 Proposal compilation 共享。Cache 实例由 `qa_build_id` 隔离；事实条目键固定 `target_kg_build_id / fact_build_id / entity_build_id / metric_build_id / metric_id / scan_policy_hash`。其中 `scan_policy_hash` 覆盖扫描版本、`compiled_scan_rows_per_metric`、graph-ready、forecast、value/unit、comparability 排除规则和确定性排序；扫描语义变化时必须提升 `METRIC_FACT_SCAN_VERSION`，因此不同 KG、上游 build、指标或扫描策略不会错误复用。

缓存只在当前 build 进程内生存，不跨 build 持久化。首次扫描后以元组快照保存事实，每次命中返回独立 dict，避免后续 operator 修改共享行。每个 `qa_pattern_compilations.sampling_summary.metric_fact_cache` 保存该 Proposal 的 hit/miss/query/loaded/reused 增量；QA build notes 和 candidate report 保存全 build 汇总及指标、policy hash。可用 `compiled_metric_fact_cache_enabled=false` 禁用存储，此时仍记录实际扫描 query 和 loaded rows。按 family 合并多指标 SQL 与批量执行多个 Proposal 是下一阶段优化，当前仍保持每个 Proposal 独立 Compilation、Logical Plan 和审计记录。

两个持久化层分别承担不同职责：

```text
qa_pattern_compilations
保存 logical plan、plan hash、source/target KG、发现/验证/采样计数和状态。

qa_compiled_bindings
保存正式 binding、binding hash、sampling stratum、semantic/execution 状态和 audit overlap。
```

Candidate 现在固定 `pattern_compilation_id / logical_plan_hash / compiler_version / compiled_binding_id / compiled_binding_hash / proposal_semantic_id`；Catalog 路径还固定跨 release 稳定的 `catalog_pattern_id`，以及 release-specific 的 `pattern_catalog_release_id / pattern_catalog_entry_id / pattern_catalog_entry_hash`。最终 `compiled_binding_match` 验证 plan 内容 hash、compiler、QA Build、proposal、target KG、binding 与 facts；`pattern_catalog_match` 额外验证 Candidate、Compilation、Catalog Entry、来源 Proposal 身份、来源 Mining Run、来源 KG 与 QA Build 的完整链。

## Published Pattern Catalog

Catalog 1.2.0 将发布身份和执行来源分开：`catalog_pattern_id` 由 Proposal semantic identity 确定，可跨 release、跨 KG 保持稳定；source Proposal、Mining Run 和 source KG 只保留 lineage。`qa_pattern_catalog_releases` 保存一次不可变发布：来源 Mining Run、来源 KG、冻结 proposal manifest hash、Catalog manifest/hash、兼容 contract、entry 数量、发布者和状态。`qa_pattern_catalog_entries` 保存完整 Proposal 执行快照，包括 Pattern Spec、Operation DAG、答案 schema、example/held-out bindings、静态 Pattern pins、通过率、score 和 entry hash。

```text
Mining Run (approved_for_qa)
→ publish-qa-pattern-catalog
→ immutable Catalog Release / Entry
→ compile against any compatible target KG
→ QA Build pins target KG + source Run + Catalog Release
```

Catalog loader 每次重算全部 entry hash 和 release manifest hash。Contract v2 除了固定 source graph schema、IR versions、scan kinds 和所需 metric 的 ontology 签名，还冻结 `semantic_operator_manifest_hash`、`operation_operator_manifest_hash`、`comparability_policy_hash`、单位与时间归一化版本、SourceDefinition schema 版本，以及 seasonal-adjustment 解释策略版本。完整的规范化 comparability policy 和两个 Operator manifest 也随 release 保存，加载时会独立重算摘要，防止只篡改声明字段。

QA Build 在插入 build row 和执行 Compilation 之前，将全部 Contract 字段与 target KG 及当前部署逐项对比；缺少指标、ontology 签名变化、策略漂移、Registry 漂移、标准化语义变化或不支持的 IR/scan kind 都会 fail closed。目标运行 Contract 同时进入 `config_hash` 并固定在 build notes；问题生成和最终验证会从 pinned policy 重新生成当前 Registry manifest，检测候选构建后的部署漂移。Catalog 1.1 / Contract v1 不再隐式兼容，必须从已批准 Mining Run 重新发布。

Compiler 2.5.0 将 `catalog_pattern_id / release_id / entry_id / entry_hash` 写入 Logical Plan，因此它们参与 `logical_plan_hash`，并继续固定 source KG 与 target KG。Compilation、Candidate 和最终 verifier 必须对这些身份逐项一致。最终 replay 从已验 hash 的 Catalog Entry 读取 Pattern Spec，不读取 live Proposal 的执行语义；即使来源 Run 后续 supersede，或 source Proposal、source KG 已不可用，已发布 Entry 仍可针对拥有不同 Fact/Entity/Metric Build IDs 的兼容 target KG 重编译。旧的 `--mining-run-id` 路径保留，并继续要求 Mining Run 与 target KG 相同；跨 KG 必须显式使用 `--pattern-catalog-release-id`。

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

图模式先生成 `canonical_semantics` 和 canonical Operation Plan，再选择受控模板。`question_generation.mode=controlled_llm` 的 `sentence_plan` 策略将 LLM 接口收敛为 **Sentence Plan + Deterministic Semantic Rendering**：verbalizer 只发送 canonical question、有限枚举的风格 schema 和候选数量，不发送答案，也不发送 `slot_map / operator_id / constraints` 让模型自我声明语义。LLM 只能返回：

```json
{
  "sentence_plans": [
    {
      "plan_version": "sentence_plan.v1",
      "tone": "analyst",
      "sentence_form": "direct_question",
      "connector": "then"
    }
  ]
}
```

`tone / sentence_form / connector` 都是 fail-closed 枚举；出现 `question`、阈值、指标、实体、时间、operator 或任意额外字段时整个 plan 无效。最终 question 由程序从 canonical template 渲染，比较方向、最高/最低、filter/rank/lookup 顺序、阈值、top-k、指标、scope 和时间始终来自 canonical contract，LLM 没有修改这些 token 的接口。

`protected_rewrite` 策略在保留同一语义边界的前提下，让 LLM 负责最终 QA 的反标准化。程序把实体、指标、期间、阈值和 top-k 替换为不可变 placeholder，并为每个 slot 构造本地等价表达白名单。模型只看到 placeholder、候选 ID 和样式标签，不看到答案或白名单对应的真实值，并返回受保护问句模板及 `surface_variant_ids`。

每个 slot 必须且只能选择一个已注册 ID。未知 ID、缺失 slot、重复 placeholder、额外数字、比较方向变化、操作顺序变化和扩展性结论都会失败。合法选择在本地解析为 `FY2023`、实体简称或指标别名等表面形式。若自由问句模板失败但变体选择合法，系统使用确定性安全模板保留 LLM 的反标准化选择，记为 `controlled_llm_surface_realization`；只有变体选择也无效时才进入确定性 fallback。

roundtrip verifier 另有独立的 deterministic Question Parser，不读取模型返回的 Contract 作为问题语义证据。Parser 将比较词绑定到对应数字附近，重新识别 `gt/gte/lt/lte/eq`、排序升降序、top-k、argmax/argmin，以及可观察的 `filter → rank → lookup` 顺序，再与 canonical Operation Plan 比较。因此结构化字段仍声称 `gt`，但 question 写成 `below 10%`，或自然语言改成 `rank → filter`，都会得到稳定的 `question_semantics:*` 错误并回退到 canonical template。生成方式、解析结果、sentence plan 和 fallback 原因保存在 sample `source_metadata.question_generation` 中。

默认模式仍是 `controlled_template`，因此离线构建完全可复现。启用 LLM 可增加句式和等价表面表达，但不改变问题语义。

`variants` 是单次请求中的候选 Plan/Rewrite 数，不是每个 Candidate 的导出样本数。QA build 独立汇总 HTTP/JSON、受控生成、反标准化有效率、实际非 canonical 采用率、fallback、时延、token、费用估算和生成方式分布，并把这些指标写入 build gate/report。即使 fallback 后 QA verifier 仍然 100% 通过，API、反标准化或 fallback 门控不达标时 build 也不能 ready。

QA generator 4.13.0 进一步把 parser 接入最终质量验证。新增关键门控 question_semantic_reparse，从持久化 template、canonical semantics 和 pinned Operation DAG 重建 contract，再重新解析数据库中的实际 qa_samples.question；它不读取生成阶段保存的 parser 结论。即使问题文本在生成后被替换而 source_metadata.question_generation.passed 仍为真，最终 verifier 也会拒绝该样本。

## 候选与样本字段

`qa_candidates` 新增：

```text
pattern_id
pattern_version
pattern_hash
operation_plan_id
operation_plan_hash
mining_run_id
pattern_proposal_id
pattern_proposal_hash
proposal_semantic_id
pattern_compilation_id
logical_plan_hash
compiler_version
compiled_binding_id
compiled_binding_hash
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
- `independent_recompute`：最终答案与重新执行 Operation Plan 的结果一致；
- `pattern_proposal_match`：proposal 必须 published，hash/score/semantic ID 必须与 Candidate 固定值一致，且 `candidate.mining_run_id == proposal.mining_run_id == qa_build.mining_run_id`；
- `compiled_binding_match`：正式 binding 必须来自成功 compilation；Candidate 与 Compilation 的 logical plan hash、compiler version、QA Build、proposal、target KG、binding hash、事实集合和输入角色必须全部匹配，并重新计算存储 Logical Plan 的 SHA-256；
- `semantic_constraint_gate`：所有绑定事实必须重新通过 pattern 声明和 comparability policy；
- `question_slot_roundtrip`：问题保留全部不可变语义槽；
- `question_answer_isolation`：问题生成器未接收答案 payload。

Scope completeness 使用实体 ID 集合等值，而非数量下界：`represented_entity_ids == expected_entity_ids`。因此同数量但替换了实体、遗漏实体或额外混入实体都会失败。

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
自动 mining 的专用预演可使用 `build-qa --mined-only --mining-run-id <approved_run>`；该模式在内存中关闭 legacy/static quotas，每个 proposal 默认只取一个 binding，并强制不激活，因此不需要复制生产连接配置。

## Pattern Mining 生产预演

对 KG `kg_20260711_062123_bc4b4394` 的最终 mining run `qamining_20260715_054441_65a5669e`：

- 扫描 70,605 个 graph-ready facts、24 个高覆盖指标；
- family-balanced 保留 100 个 proposal，88 个通过评分；
- approved 分布：cross-metric 25、scope rank follow-up 22、temporal aggregation 12、temporal extrema follow-up 29；
- rejected proposal 保留 rejection reasons，不进入 compiler。

mined-only smoke build `qa_build_20260715_055031_03f5d0ef` 从 88 个 approved proposals 各取一个 binding：88/88 candidates eligible，88/88 samples 通过 proposal hash、Operation DAG 中间结果、独立复算、evidence、question slot 和 split gate；build 保持非激活。难度分布为 medium 25、hard 12、expert 51，四种唯一 operator sequences，pattern entropy 6.459432。

引入可执行语义门控、完整时间序列 key 与严格 scope universe 后的 mining 1.3.0 最终 run `qamining_20260715_113452_e71c949b` 扫描 70,605 个 facts 和 24 个指标，将任意共现组合收敛为 29 个 proposal、17 个 approved：cross-metric 3、temporal aggregation 12、temporal follow-up 2。当前生产池没有满足全部严格条件的自动 scope proposal，因此不会降低门控强行补量。非激活 smoke build `qa_build_20260715_113526_2d216cfb` 生成 51 个 candidate，51/51 eligible 且 51/51 通过最终 verifier 与 build gate；其中 cross-metric 9、multi-period average 36、temporal follow-up 6。

mining 1.4.0 在此基础上增加 proposal 生命周期、example/held-out 独立执行验证、人工审核状态、结构重叠度和 binding 多样性指标。1.3.0 的 `approved` 记录是历史基线，不会被 1.4.0 的 loader 当作 `published` proposal 消费；必须重新挖掘并通过新门控。

最终生产验证 run `qamining_20260715_120154_f83156d5` 扫描同一 KG 的 70,605 个 facts 和 24 个指标，生成 29 个 proposal：17 个完成生命周期并进入 `published`，12 个因支持度和总评分不足停在 `proposed`。17 个发布 proposal 的 semantic、全量 operation、saved examples 与 held-out 最低通过率均为 1.0；binding diversity 范围为 0.170543—0.759259。`static_pattern_overlap` 全部为 1.0，准确反映当前 mined motif 与既有静态模式结构等价，因此不会再把指标数量误算成 novelty。

最新非激活 smoke build `qa_build_20260715_120218_cc593c18` 只消费上述 17 个 `published` proposal，生成 17/17 eligible candidates，17/17 samples 通过最终 verifier 和 build gate，且没有替换 active QA。

Pattern Compiler V2 最终生产 smoke build `qa_build_20260715_123338_b67933e9` 对相同 17 个 Proposal 在完整 pinned KG 上重新执行查询，每个 Proposal 最多采样 10 个正式 binding：17/17 compilations 成功，共发现 53,859 个 bindings，并全部通过 Proposal 原始 semantic constraints 与 Operation DAG 的权威复验；分层采样 170 个 compiled bindings，其中 167 个不是 mining 审计样例。正式 QA 为 170/170 eligible、170/170 verifier passed，覆盖 550 个唯一 Fact IDs，其中 539 个不在审计样例事实集合中；build gate passed 且保持非激活。候选报告直接保存完整 `pattern_compilation_summary`。

mining 1.5.0 增加 Mining Run 发布门控。QA 构建不再自动消费最新成功 run，而是要求显式固定一个 `approved_for_qa` run；run 审核人、批准人、生命周期事件和 supersede 关系均持久化。每个 QA build 直接保存 `mining_run_id`，同一 motif 在不同 run 中使用独立 Proposal ID，避免后续 mining 覆盖历史构建输入。

P0-6 生产迁移验证将 `qamining_20260715_120154_f83156d5` 依次推进为 `reviewed` 和 `approved_for_qa`。显式固定该 run 的非激活 smoke build `qa_build_20260715_130053_f8edba13` 完成 17/17 compilations，扫描并复验 53,859 个 bindings，采样 17 个非审计 binding；17/17 candidates eligible、17/17 samples 通过 verifier 与 build gate，且 `qa_builds.mining_run_id` 与候选报告均记录该固定 run。

mining 1.6.0 生产验证 run `qamining_20260715_133929_f9a91953` 使用分层 pool 扫描 58,993 个 facts 和 24 个指标，生成 30 个 proposal，其中 25 个 published；所有 published proposal 的 semantic、operation、saved-example 和 held-out 最低通过率均为 1.0。跨指标、时间均值和时间极值 follow-up 均识别为静态 pattern 的新 bindings，不再重复注册语义相同的 pattern。

同一 run 的 graph-native inventory 观测到 707,835 条 DerivedFact composition 边、496,131 条 EntitySet scope 路径、518,810 条时间层级边，以及 658,535 个具备完整 source/definition/raw-object 来源链的 Fact 根节点；当前 KG 尚无跨来源 equivalence/conflict/supersedes 边，因此该 motif 明确记录为 `unsupported`。run 保持 `success`，未进入 `approved_for_qa`。兼容 smoke build `qa_build_20260715_134139_447e1ed6` 继续固定旧批准 run，17/17 samples 通过并保持非激活。

Semantic Operator Registry 生产验证先对 7 个 active pattern 各预演最多 25 个 binding，共发现 173 个且 7/7 pattern 执行成功。随后非激活 build `qa_build_20260715_144652_b1fd998c` 固定旧批准 run，5 个 compilation 共发现 570 个 binding，570/570 通过新 semantic gate 与 Operation DAG 复验；采样的 5/5 candidates eligible、5/5 samples verifier passed，build gate passed 且未替换 active QA。

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

自动 mining 仍不是无约束的通用子图枚举。DerivedFact 输入追踪、Fact provenance、calendar/fiscal hierarchy membership 和 DerivedFact scope composition 已从 inventory 晋升为可执行 Proposal；数值时间聚合继续复用事实 IR。下一阶段重点是历史 membership 的有效期、跨来源 equivalence/conflict/supersedes 的语义门控、Catalog 兼容性声明，以及 proposal、operator-composition、metric-pair 和 scope holdout。

## 2026-07-17 完整生产验证

Mining 2.2.0、Compiler 2.7.0、Catalog 1.2.0 和 Generator 4.18.0 已完成同 KG 与跨 KG 的完整生产验证。固定 Mining Run `qamining_20260717_133818_f495a490` 发布为 Catalog `qacatrelease_e2f9b7ce79e56a8b58f71dfb`；32/32 Pattern 在源 KG 和非激活目标 KG 上均成功重新编译，各自发现 80,285 个 binding，4,073 个通过语义与执行门控，最终生成 303/303 verifier-passed QA。

6 次 graph scan 共登记 2,906,120 个根节点，root/stratum inventory coverage 为 100%；在明确记录的 1,200-root 分层评估预算内执行 motif expansion。源/目标结果的 306 个 `binding_hash`、303 个 `stable_candidate_id`、303 个 `stable_qa_id` 和 303 个 `semantic_cluster_id` 全部精确一致。

独立问题语义解析能拒绝 `highest -> lowest` 的方向篡改，并在事务回滚后保持正式样本不变。两个 PostgreSQL 连接并发审批 Mining Run 时，最终严格保留一个 `approved_for_qa` 和一个 `superseded`。完整测试为 98 passed，Ruff passed；所有验证 build 均为非激活，生产 KG/QA 指针未变化。详细数据见 `data/audit/qa_production_validation_20260717/production_validation_report.md`。

## Question Parser 版本化契约

Generator 4.19.0 将有限词表 Parser 的支持边界显式版本化。Question Parser 1.0.0 的 manifest 冻结支持语言、支持模板 ID、模板 required-slot contract、比较词表，以及 operator/rank/extrema/threshold/top-k 正则；任何规则变化都会改变 `question_parser_manifest_hash`。

`qa_builds` 固定 `question_parser_version` 和 `question_parser_manifest_hash`，build notes 保存完整 manifest；每个样本还保存实际使用的 `supported_language` 和 `supported_template_id`。最终 verifier 在语义重解析前执行关键门控 `question_parser_contract`，版本、manifest、语言、模板或样本元数据任一漂移都会 fail-closed。

模板与 Parser 使用双向契约测试：注册模板必须全部被 Parser 支持，Parser 声明的模板必须全部存在，并逐模板执行确定性渲染和 slot round-trip。生产 smoke build `qa_build_20260717_145056_528e2734` 的 `question_parser_contract` 与 `question_semantic_reparse` 均通过，保持非激活。当前完整测试为 100 passed。详细报告见 `data/audit/qa_production_validation_20260717/question_parser_contract_report.md`。

## 2026-07-18 复杂度结构优化

本轮将复杂 QA 的供给与总样本量解耦。`scope_top_ks` 从单一的 top-3/top-5 扩展为 top-1 到 top-5；增长率和负债率阈值继续由白名单场景控制。每个场景都形成不同的 Operation Plan 参数，但共享完整行业 universe，不通过截断 scope 或降低验证标准补量。`top-1` 表示“找出行业冠军后查询第二指标”，仍是完整的 `rank → secondary lookup` 两阶段任务。

Semantic Operator Registry 1.2.0 将操作计划中的实际阈值作为本次场景阈值，并验证它属于配置允许集合。跨指标期间使用 fiscal/calendar frequency identity 对齐，而不是要求 `period_end` 字符串完全相同；不同 binding 可以分别保持 `period_flow` 与 `point_in_time` 的内部时间口径，因此收入排名后查询资产不会被错误拒绝。声明了全局 `time_basis same` 的 Pattern 仍执行严格全局一致校验。

复杂度质量门控同时检查最低样本数和最低比例，避免 Easy/Medium 总量增长时稀释 Expert/Research。专用非激活配置 `config/profiles/prod_qa_complex_balance_validation.json` 关闭旧事实型配额，只验证四类多阶段任务。生产 KG `kg_20260711_062123_bc4b4394` 的最终非激活 build `qa_build_20260717_165208_5e528891` 结果为：

- 998 candidates，998 eligible，998 verifier passed，零 semantic rejection；
- `filter → rank` 200、multi-factor screening 300、`rank → secondary lookup` 400、`argmax → lookup` 98；
- Expert 226（22.65%），Research 772（77.35%）；
- train_complex 696、dev_complex 142、test_complex 160；
- graph-pattern 数量、Expert/Research 数量与比例门控全部通过；
- build 保持非激活，不改变正式 QA 指针。

预演报告位于 `data/audit/qa_complex_balance_preflight_20260718_v2/`，最终构建报告位于 `data/audit/qa_complex_balance_validation_20260718_v3/`。

## Typed Edge Walk Mining

QA V4 现在在既有 motif mining 旁增加 Typed Edge Walk 发现子系统，但不建立新的 QA 数据模型：

```text
Operation Macro
→ Typed Relation Walk
→ QueryGraphIR
→ Binding Query IR V2
→ Pattern Proposal
→ 现有 Compiler / Binding Executor
→ Operation Plan
→ Evidence Finalizer
→ Question / Independent Verifier
```

实现位于 `finraw/qa/graph_walk/`。Relation Schema Registry 对允许的源节点类型、关系、方向和目标节点类型执行 fail-closed 校验；Operation Macro Registry 固定答案目标、所需角色、金融约束、Operator DAG 和答案结构。QueryGraphIR 将图上的 walk、branch、join、role predicate、scope coverage、投影和 evidence policy 一并纳入稳定 hash，从而让不同游走顺序得到的同义结构可以去重。

Binding IR V2 新增：

```text
filter_graph_role
deduplicate_graph_role
require_graph_roles_contiguous
assert_role_key_equal
assert_role_key_relation
require_role_coverage
project_graph_binding_v2
```

复杂 follow-up 不在 Operation 执行中动态查询 KG。Binding 阶段预先绑定完整候选事实超集，Operation 阶段通过排名或极值结果选择对应事实。所有 Operator 输出统一 `lineage`；Evidence Finalizer 据此拆分 `required_evidence`、`context_evidence` 和 `discarded_evidence`。最终 verifier 会独立重放 QueryGraph hash、边、方向、角色类型、角色谓词、join、scope、答案血缘和 evidence finalization。

首批启用三个 Macro：

1. `temporal_extreme_followup_provenance`：时间序列极值 → 同期第二指标 → 来源。
2. `scope_filter_rank_followup`：完整行业 scope → 增长筛选 → 利润率排名 → 排名实体负债率查询。
3. `derived_fact_time_source_trace`：DerivedFact → 输入事实 → 财政时间 → 原始来源。

Mining observation 分开报告：

- `structural_completion_rate`：图结构和语义约束完整率；
- `answer_yield_rate`：完整结构中可产生非空答案的比例；
- `unique_answer_rate`：每个语义 Binding 是否只有一个确定性答案；
- root/evaluation/stratum coverage：扫描预算和覆盖范围。

重复图展开路径先按事实、实体、scope、输入角色和 QueryGraph hash 合并。同一语义 Binding 的重复路径不会降低答案唯一率；只有同一 Binding 得到多个不同答案才视为 ambiguity。

生产 smoke 使用 pinned KG `kg_20260711_062123_bc4b4394`，Mining Run 为 `qamining_20260719_163705_5b1c10e6`。3/3 Walk observations 被接受并生成 3 个 `execution_validated` Proposal：

| Macro | 唯一可回答 Binding | 结构完整率 | 答案产出率 | 答案唯一率 |
| --- | ---: | ---: | ---: | ---: |
| Derived trace | 40 | 100% | 80.00% | 100% |
| Scope filter/rank/follow-up | 7 | 100% | 25.93% | 100% |
| Temporal extreme/follow-up | 6 | 100% | 100% | 100% |

三个 Proposal 的 semantic、operation、example 和 held-out 检查均为 100%。本次 run 保持 `success` 且 Proposal 保持 `manual_review_status=pending`，没有自动发布、没有替换现有 `approved_for_qa` Mining Run，也没有改变 active QA 指针。详细结果位于 `data/audit/qa_typed_walk_smoke_20260719_v5/`。

运行命令：

```bash
python -m finraw.cli \
  --config config/profiles/prod_qa_typed_walk_smoke.json \
  mine-qa-patterns \
  --kg-build-id kg_20260711_062123_bc4b4394 \
  --output-dir data/audit/qa_typed_walk_smoke_20260719_v5
```

该流程完全由本地 KG、确定性模板和 verifier 驱动，不需要 LLM API。后续若启用语言多样化，仍应先查询 provider 的可用模型并选择兼容模型；模型只负责表层表达，QueryGraph、Operation Sequence、阈值、scope 和答案保持程序固定。
