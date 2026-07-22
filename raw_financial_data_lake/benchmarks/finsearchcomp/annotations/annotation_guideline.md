# FinSearchComp Alignment Annotation Guideline

## Purpose

This taxonomy treats the official FinSearchComp release as an evaluation-only
distribution reference. Official prompts, answers, translations, and prompt
rewrites must not enter training exports. Rule annotations are proposals for
review, not benchmark ground truth beyond the official `label` field.

## Stable Identity

`prompt_id` is not globally unique across the Global and Greater China labels.
Use the composite key:

```text
official_item_id = label + "::" + prompt_id
```

The frozen revision and both raw and Parquet checksums must be retained with
every analysis release.

## Benchmark Task

### T1

Time-sensitive retrieval whose answer changes after dataset publication. T1 is
frozen for completeness but excluded from historical QA distribution fitting.

### T2

A fixed historical lookup with a directly recoverable answer. Typical evidence
contains one entity, one period, and one or two facts. A direct difference,
ratio, or growth calculation may remain T2 when it does not require a range
scan, complete scope, or multi-stage investigation.

Review fiscal/calendar basis, instant versus duration, restatement policy,
GAAP/non-GAAP definition, unit, currency, and requested precision.

### T3

A fixed historical investigation requiring at least one strong trigger:

- three or more periods;
- two or more answer-relevant entities;
- a multi-stage operation plan;
- a complete entity scope;
- multiple answer sources;
- a list, table, ranking, or screening answer;
- unit, currency, or calendar normalization across inputs.

## Controlled Fields

Use only registered values for:

- `topic`: corporate fundamentals, market data, macroeconomics, industry and
  alternative data, fund and portfolio, or other financial;
- `answer_type`: numeric, boolean, entity, period, entity and value, period and
  value, table, or ranked table;
- `operation_families`: lookup, difference, ratio, growth, aggregate, temporal
  extreme, filter, rank, date distance, or multi-source synthesis;
- `rubric_type`: exact, rounding, relative tolerance, absolute tolerance,
  range, or structured.

Unknown values should remain explicit rather than being guessed.

## Review Workflow

1. Accept or correct task, market, language, and topic.
2. Verify entity, metric, time, source, and answer structure.
3. Reconstruct the minimum operation sequence in execution order.
4. Record scope completeness and normalization requirements.
5. Verify that the rubric captures all output fields, order, and tolerance.
6. Set `manual_review_status=approved` only after the above checks.

T3 items require manual review of `operation_families`, `operation_depth`,
`answer_type`, and scope completeness. A stratified T2 sample should also be
reviewed across market, topic, language, and rubric types.

## Contamination Policy

Official items use `usage=evaluation_only` and `contamination_guard=true`.
Exact normalized hashes are checked automatically. Semantic near-duplicate
review is still required before publishing a training release.

