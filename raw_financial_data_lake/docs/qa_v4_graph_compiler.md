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

同一语义模式可以跨 Mining Run 和 KG build 跟踪支持度变化，而不同快照不会覆盖。若语义与静态 registry 重合，proposal 标记为 `known_pattern_binding` 并复用静态 `pattern_id`；candidate 层再按事实集合、操作 DAG、时间、实体、指标和答案 schema 去重，避免静态与自动路径重复导出同一任务。

Mining 1.6.0 还直接扫描 KG topology，将 `DerivedFact → Fact`、`DerivedFact → EntitySet → Entity`、时间层级、事实来源链及跨源等价/冲突/修订关系记录到 `qa_graph_motif_observations`。这些记录是可审计的 discovery inventory：有支持度时标记 `observed`，无支持度时标记 `unsupported`，不会未经语义与执行验证直接晋升为 QA Pattern。

每个 `qa_pattern_proposals` 记录：

```text
motif_signature / pattern_spec / operator_dag_template
binding_examples / heldout_bindings / support_count
support_score / completeness_score / financial_value_score
complexity_score / novelty_score / total_score
semantic_constraint_pass_rate / operation_execution_pass_rate
example_binding_pass_rate / heldout_binding_pass_rate
static_pattern_overlap / binding_diversity_score
manual_review_status / lifecycle_events / status
rejection_reasons / proposal_hash
```

Proposal 采用 `proposed → semantic_validated → execution_validated → reviewed_approved → published` 生命周期。评分只负责排序，不能授予发布资格。所有保存的 binding examples 必须 100% 执行成功，额外的确定性 held-out bindings 必须达到至少 99% 执行通过率；当 `require_manual_review=true` 时，proposal 会停在 `execution_validated`，直到 `review_pattern_proposal()` 记录审核通过。只有 `published` proposal 才能由 `pattern_compiler.py` 编译并进入正式 QA build。QA candidate 同时固定 `mining_run_id`、`pattern_proposal_id`、`proposal_hash` 和 `pattern_score`，避免后续静默修改 proposal 语义。

Example 与 held-out 按 binding 内容哈希确定性切分，二者互斥；held-out 不参与 candidate 生成。挖掘阶段使用与正式 QA 相同的 `materialize_plan()` 和 `execute_plan()` 逐条重放 Operation DAG，并持久化错误、输出 hash 和两组通过率。`static_pattern_overlap` 由节点类型、边类型、operator、任务和答案结构与静态 registry 做 Jaccard 比较，`novelty_score` 取其补集；`binding_diversity_score` 则衡量实体、期间与 scope 的真实变化，不再用指标数量代替新颖度。

`semantic_constraints` 不是说明性标签。`semantic_constraints.py` 在三个阶段执行同一验证函数：mining binding 在计入 support 前校验，candidate 在进入 eligible pool 前复验，最终 verifier 再从 pinned facts 与持久化 pattern spec 独立执行。门控覆盖 registered comparable/follow-up metric pair、statement/period type、来源定义兼容类、financial scope、frequency、seasonal adjustment、vintage、forecast 与 graph-ready 状态。每个 check 保存 observed/expected，失败使用稳定的 `semantic_constraint:<check_name>` 原因码；proposal 另存 evaluated、accepted 和 rejection-count 诊断。

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

Mining Run 采用 `running → success → reviewed → approved_for_qa → superseded` 生命周期；失败任务进入 `failed`。正式 QA build 必须显式传入 `mining_run_id`，并同时校验 run 属于 pinned KG 且状态为 `approved_for_qa`，不会查询或回退到“最近一次成功 run”。批准同一 KG 的新 run 时，旧的 `approved_for_qa` run 自动转为 `superseded`。

`qa_builds.mining_run_id`、build notes 中的 selected run、proposal manifest 和 candidate 级 proposal/binding ID 共同形成审计边界。Proposal ID 以 Mining Run 为作用域，`proposal_hash` 保持内容身份，因此重复 mining 不会覆盖历史 run 的 Proposal。开发环境可同时设置 `auto_run=true` 与 `auto_approve_for_qa=true` 做端到端预演；默认 `auto_approve_for_qa=false`，正式配置不得用它替代审核。

## Pattern Compiler V2

Proposal 的审计样例与正式 QA 输入已经分离：

```text
published Pattern Proposal
→ LogicalPatternPlan
→ scan pinned KG Fact nodes
→ entity / metric / period joins
→ family-specific group / window / scope joins
→ semantic constraint gate
→ Operation DAG execution gate
→ deterministic stratified sampling
→ qa_compiled_bindings
→ QA candidate
```

`compile_logical_pattern()` 不读取 `binding_examples` 来生成问题。它把 graph node/edge constraints、指标角色、semantic constraints 和 operator template 编译成版本化查询 IR，并固定 source proposal KG、target KG、fact/entity/metric/source-definition builds、scan predicates、关系操作和采样策略。当前 IR 支持 cross-metric join、连续时间窗口、双时间序列 period join 与行业 complete-case scope join。

`binding_executor.py` 解释该 IR，默认扫描目标指标在 target KG 中的全部 graph-ready facts；`compiled_scan_rows_per_metric=0` 表示全量，只有显式配置正数时才施加运维上限。执行器先发现并验证全部 binding 候选，再进行确定性分层采样。审计样例 hash 只用于统计 overlap 和优先选择非样例 binding，不会作为查询输入。

两个持久化层分别承担不同职责：

```text
qa_pattern_compilations
保存 logical plan、plan hash、source/target KG、发现/验证/采样计数和状态。

qa_compiled_bindings
保存正式 binding、binding hash、sampling stratum、semantic/execution 状态和 audit overlap。
```

Candidate 固定 `pattern_compilation_id / compiled_binding_id / compiled_binding_hash`。最终 `compiled_binding_match` 会验证 compilation 成功、proposal/hash 一致、target KG 等于 QA pinned KG、binding hash 一致、source facts 与 input bindings 完整一致。Proposal 的 source KG 可以与 compilation target KG 分开记录，为同一逻辑 Pattern 在新 KG build 上重新编译保留了版本边界。

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

图模式先生成 `canonical_semantics`，再选择受控模板。`question_generation.mode=controlled_llm` 时，verbalizer 只向配置的 LLM 发送 canonical question、允许公开的语义和 immutable slots，绝不发送答案。LLM 必须返回结构化结果：

```json
{
  "question": "...",
  "slot_map": {"scope": "...", "top_k": "3"},
  "operator_id": "filter_then_rank",
  "constraints": [{"position": 0, "operator": "filter", "params": {}}]
}
```

校验器同时检查字符串槽位和结构化语义契约：operator 顺序、阈值、比较方向、top-k 和每步 params 必须与 canonical Operation Plan 完全一致。只保留实体名称但将“大于”改成“小于”，或将 `filter → rank` 改成 `rank → filter`，都会回退到确定性模板。

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
- `pattern_proposal_match`：proposal 必须 published，hash/score/KG build 必须与 candidate 固定值一致；
- `compiled_binding_match`：正式 binding 必须来自成功 compilation，且 proposal、target KG、hash、事实集合和输入角色全部匹配；
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

自动 mining 当前采用“分层事实 motif + 图拓扑观测 + KG 自动角色绑定”，不是无约束的通用子图枚举。下一阶段应从 `qa_graph_motif_observations` 中选择支持度和业务价值达标的 topology motif，编译为带语义门控的 binding query，再进入现有 proposal 生命周期。其余重点是 provenance trace 问题、历史 membership、跨来源冲突路径，以及 proposal、operator-composition、metric-pair 和 scope holdout。
