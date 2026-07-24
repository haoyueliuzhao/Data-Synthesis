# FinSearchComp T2/T3 Distribution Alignment

## Design Goal

FinSearchComp is an external benchmark and distribution reference, not a source
of training prompts. Alignment has three independent success conditions:

1. distribution coverage resembles the official T2/T3 task structure;
2. every synthetic answer still passes the existing operation and evidence
   verifier;
3. training on the aligned data improves the untouched official benchmark.

Only the first two are implemented in this repository. Benchmark gain remains
an external model experiment and is never inferred from distribution distance.

## Pipeline

```text
Pinned official release (evaluation only)
  -> deterministic native statistics
  -> reviewable official taxonomy

Passed QA samples
  -> structural T2/T3 classifier
  -> generation-chain label
  -> persistent qa_distribution_labels

Official taxonomy + current taxonomy
  -> coverage matrix
  -> TVD / Jensen-Shannon distance
  -> gap manifest
  -> agent-input and hidden-gold views
```

The classifier uses facts and operation plans rather than wording alone. T3 is
triggered by long or multi-entity/multi-period windows, multi-source joins,
complete scopes, at least two reasoning operations after retrieval, or structured
multi-item answers. A lookup followed by one difference, ratio, or growth
calculation remains T2. Entity count alone is not a T3 trigger: a direct same-period comparison between
two entities remains T2 unless another complex-investigation condition applies.
Low-depth fixed historical queries remain T2.

## QA Chain Mapping

| Generation chain | Detection | Typical alignment |
| --- | --- | --- |
| Fact QA | no pattern and no derived input | T2 |
| DerivedFact QA | derived input without graph pattern | T2 or T3 |
| Static Graph Pattern | registered pattern without proposal | T2 or T3 |
| Automatic Pattern Mining | `pattern_proposal_id` present | mainly T3 |
| Typed Edge Walk | walk pattern identity | mainly T3 |

The chain label records how the task was discovered. It does not determine T2
or T3 by itself.

## Data Contract

Each current QA receives a versioned label containing:

```text
benchmark_task, difficulty, market_subset, language, topic, subtopic
entity_type, metric_families, source_classes
time_basis, frequency, period_count, time_span_months
answer_type, operation_families, operation_depth, scope_size
rubric_type, generation_pipeline
structural_features, completeness_checks, classification_reasons
```

The label is persisted in `qa_distribution_labels`. Generated artifacts retain
two separate views:

- Agent input: natural question and allowed tool classes;
- Hidden gold: facts, documents, operation plan, entities, metrics, and time.

Internal IDs and KG paths are not exposed in the agent question.

## Frozen Official Baseline

- Revision: `1fd1beea75482e2dd5e2be8f618195d9c6aff176`
- Rows: 635
- T1: 244; T2: 219; T3: 172
- Global: 337; Greater China: 298
- Historical alignment population: 391 T2/T3 items
- Raw SHA-256:
  `6437a6dae907ec81002bd817dafc26c3e46e6b6edfde700f22645b1e2aa208c4`

Official `prompt_id` values repeat across market labels, so the frozen identity
is `(label, prompt_id)`. All 635 semantic annotations currently have status
`rule_preannotated` and require human review.

## Current Production Findings

The active build `qa_build_20260712_023651_7adad081` contains 64,221 passed
samples:

- T2: 33,481; T3: 30,740;
- Fact QA: 27,278; DerivedFact QA: 36,943;
- exact normalized overlap with official prompts: 0;
- official category coverage across the audit matrix: 45.35%.

The global T2/T3 ratio is close to the benchmark, but this is not sufficient
alignment. Major conditional gaps remain:

- no Greater China samples in the active build;
- only English questions;
- narrow answer schemas, especially lists, dates, entities, and tables;
- weak rubric coverage beyond numeric tolerance;
- insufficient T3 operation, source, and long-window coverage;
- units are explicit in 17.74% and requested precision in 0% of questions.

Two validated non-active capability builds add important structures:

- automatic Pattern Mining: 303 samples, 113 T2 and 190 T3;
- Expert/Research static graph patterns: 998 samples, all T3.

Typed Edge Walk has implementation and tests but no retained production sample,
so its current distribution contribution is zero.

## Benchmark Task and Difficulty Cross-Audit

`benchmark_task` and `difficulty` describe different properties and are audited
jointly. Every alignment report includes this matrix:

| Benchmark Task | Easy | Medium | Hard | Expert | Research |
| --- | ---: | ---: | ---: | ---: | ---: |
| T2 | count | count | count | count | count |
| T3 | count | count | count | count | count |

The audit computes three diagnostic ratios:

```text
T3 easy / all T3
T2 (expert + research) / all T2
T3 (hard + expert + research) / all T3
```

Production profiles currently require review when T3 easy exceeds 15%, T2
expert/research exceeds 5%, T3 hard-or-higher falls below 50%, or the T3
task share falls outside the production 40%-55% band. The report is
marked `review_required` and identifies the generation pipelines and T3
classification reasons contributing to suspicious cells. These diagnostics do
not relabel samples by difficulty; they expose disagreement between the task
classifier and the independent difficulty policy for correction.

The matrix is written to `benchmark_task_difficulty_matrix.csv`, included in the
JSON and Markdown reports, and `difficulty` is persisted in
`qa_distribution_labels` under alignment contract v1.4.

## 1,000-Item Pilot Cross-Audit

Alignment v1.3 exposed 180 `T3 easy` samples, all from DerivedFact QA and all
classified through the old `operation_depth>=2` rule. They were simple
`lookup + one calculation` tasks rather than complex investigations.

Alignment v1.4 excludes retrieval from reasoning depth. The corrected matrix is:

| Benchmark Task | Easy | Medium | Hard | Expert | Research | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| T2 | 678 | 0 | 45 | 0 | 0 | 723 |
| T3 | 0 | 54 | 87 | 74 | 62 | 277 |

The cross cells are now internally consistent: T3 easy is 0%, T2
expert/research is 0%, and T3 hard-or-higher is 80.51%. However, corrected T3
share is only 27.70%, below the 40%-55% production band. The next release must
add genuinely complex tasks through multi-stage Automatic Mining and Typed Walk
rather than relabeling one-step DerivedFact tasks.

## Quality Interpretation

The alignment command only consumes `qa_samples.validation_status='passed'`.
This preserves existing fact, operation replay, evidence, scope, and question
round-trip gates. Distribution similarity cannot override those gates.

The generated gap manifest is a scheduler input, not permission to fabricate
unsupported data. A requested cell with `source_capability_status=not_yet_present`
requires new source coverage or a smaller target, not relaxed verification.

## Commands

```bash
python -m finraw.cli freeze-finsearchcomp
python -m finraw.cli analyze-finsearchcomp
python -m finraw.cli --config config/profiles/prod_qa_validation.json \
  align-finsearchcomp \
  --qa-build-id qa_build_20260712_023651_7adad081 \
  --output-dir data/audit/finsearchcomp_alignment_active_v1
```

## Remaining Validation

Before using the gap manifest for a release:

1. manually review all T3 and a stratified T2 sample;
2. add semantic near-duplicate contamination checks;
3. build a new combined QA release containing validated graph and walk tasks;
4. run entity-, time-, pattern-, and market-disjoint internal evaluation;
5. run the untouched official T2/T3 benchmark and report model deltas;
6. compare process metrics for source authority, evidence recall, tool choice,
   unit alignment, time alignment, calculation, and citations.



## Contamination Guard 2.0

污染检测不再只比较 normalized exact hash。每次对齐同时生成：

1. normalized exact question hash；
2. question skeleton hash，实体、年份、数值、单位和指标槽位被规范化；
3. entity-metric-time slot-normalized signature；
4. normalized Operation Program signature；
5. 本地中英文 word/character n-gram embedding cosine near-duplicate；
6. contamination_manual_review.jsonl 和 contamination_exclusion_manifest.jsonl。

Operation Program 相同只作为风险信号，不会单独判定污染。Exact Match、完整槽位同构，
或“高 embedding 相似度 + Operation Program 一致”会进入 blocked exclusion manifest；
中等相似或仅骨架一致进入人工复核；即使没有样本达到阈值，也会抽取 embedding 最相近的
Top-N 样本做校准复核，并报告相似度 P50/P90/P95/P99/Max。所有 backend、维度、阈值和
fingerprint 版本都写入 alignment report，确保历史审计可复现。只要人工复核队列非空，训练发布门保持
pending_manual_review；存在硬污染时为 failed。官方题目改公司、改年份或做同义改写后，
不得作为训练样本发布。
