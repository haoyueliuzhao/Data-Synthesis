# QA Advanced Automatic Chains

## Purpose

The QA build must not reach a T3 target mainly by increasing pre-authored DerivedFact and Static Pattern instances. Automatic Pattern Mining and Typed Edge Walk are treated as first-class production pipelines, measured separately from Fact QA, DerivedFact QA, and Static Graph Pattern QA.

The production identity is derived from persisted candidate lineage:

```text
Fact QA
DerivedFact QA
Static Graph Pattern
Automatic Pattern Mining
Typed Edge Walk
```

Typed Walk is classified before generic mined proposals because every walk candidate also carries a Pattern Proposal ID.

## Allocation Policy

Pattern proposals no longer share one global candidate cap. Candidate allocation is resolved in this order:

```text
motif-family limit
→ Typed Walk proposal limit
→ generic mined-proposal limit
```

This prevents high-support temporal aggregation motifs from consuming the entire automatic quota while low-support but more complex walk motifs receive only a handful of examples.

The current production families use these caps:

| Motif family | Candidate cap per proposal |
| --- | ---: |
| cross-metric comparison | 4 |
| temporal aggregation | 6 |
| temporal extrema follow-up | 8 |
| scope rank follow-up | 8 |
| walk temporal follow-up | 12 |
| walk scope analysis | 12 |

## Typed Walk Coverage

Typed Walk mining now registers three temporal follow-up macros and one scope macro for production:

```text
revenue peak → operating cash flow → provenance
revenue peak → net income → provenance
asset peak → liabilities → provenance
scope → revenue-growth filter → margin rank → debt-ratio follow-up
```

All temporal variants reuse one typed financial macro family. Primary and secondary metrics are read from role predicates, so adding a financially approved pair does not require duplicating explorer logic.

Every walk still passes:

```text
relation schema validation
→ root-coverage scan
→ structural completion
→ semantic constraints
→ operation execution
→ unique-answer validation
→ example and held-out validation
→ proposal publication
→ target-KG recompilation
```

## Distribution Gates

Release gates are evaluated on passed QA samples, not raw proposal counts or candidate previews.

| Market profile | Automatic Mining | Typed Walk | Combined advanced automatic | Fact QA maximum | Single Fact maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Global | >=12% and >=60 | >=1% and >=5 | >=15% | <=35% | <=35% |
| Greater China | >=15% and >=80 | >=5% and >=30 | >=20% | <=35% | <=35% |

The asymmetric Typed Walk target reflects measured KG support. Greater China currently has denser annual company series and industry scopes; Global walk coverage is constrained by complete follow-up facts. A symmetric quota would reward weak or incomplete bindings.

## Candidate Preview

The candidate preview uses KG `kg_20260723_201644_68e04b9a` and mining run `qamining_20260724_030538_a9dd992d`. Mining `2.4.0` then reproduced the exact 24-pattern semantic set in `qamining_20260724_031541_72f64782`, which is the production-approved run.

| Scope | Candidates | Automatic Mining | Typed Walk | Combined advanced automatic | Fact QA |
| --- | ---: | ---: | ---: | ---: | ---: |
| Global | 471 | 15.29% | 1.49% | 16.77% | 30.79% |
| Greater China | 511 | 17.81% | 8.02% | 25.83% | 28.38% |
| Combined | 982 | 16.60% | 4.89% | 21.49% | 29.53% |

The prior released baseline was 1.6% Automatic Mining and 0.5% Typed Walk. The preview therefore raises the combined advanced-automatic share from 2.1% to 21.49%, while reducing Fact QA from nearly half to below 30%.

This is a candidate-only validation. It does not claim a released distribution until question realization, parser validation, independent verification, split assignment, and final build gates have passed.

## Audit Requirements

Every split report and diversity report records:

```text
generation_pipeline_counts
generation_pipeline_ratios
advanced_automatic_pipeline_ratio
```

The final report must preserve the full funnel:

```text
candidate attempted
→ candidate eligible
→ binding compiled
→ operation replay passed
→ canonical QA materialized
→ LLM rewrite passed
→ parser and evidence checks passed
→ released sample
```

This keeps a high final pass rate from hiding rejected proposals, failed bindings, or LLM fallbacks.
