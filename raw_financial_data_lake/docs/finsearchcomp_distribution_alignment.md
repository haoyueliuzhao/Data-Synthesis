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
triggered by multi-period, multi-entity, multi-source, complete-scope,
multi-stage, or structured-answer requirements. Low-depth fixed historical
queries remain T2.

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
benchmark_task, market_subset, language, topic, subtopic
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

