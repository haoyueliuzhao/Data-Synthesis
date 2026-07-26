# QA Release Quality Optimization

## 1. Objective

This revision addresses the two highest-impact defects found in the 3,000-item
quality-screened release:

1. machine-oriented output contracts were leaking into user questions;
2. scope questions did not carry a stable, independently verifiable universe.

It also prevents a successfully written diagnostic file from being treated as a
training-ready release when distribution or quality contracts are not met.

## 2. Output Contract Separation

The QA record now separates two contracts:

```text
Question-visible financial request
        !=
Hidden answer and evaluator contract
```

The hidden contract retains unit, precision, output schema, ordering, row
completeness, and tolerance requirements. The question only exposes a condition
when it is financially necessary. The `financial_minimal` profile defaults are:

```text
unit visibility:               0%
precision visibility:          0%
structured format visibility:  0%
period format visibility:      0%
entity format visibility:      0%
```

Units are omitted from the question surface in the current quality profiles.
Answer matching still uses the complete hidden unit, currency, precision,
ordering, and tolerance contract. This removes repetitive machine-oriented
suffixes without weakening deterministic validation.

New profiles:

```text
config/profiles/prod_qa_deepseek_v4_global_quality_v10.json
config/profiles/prod_qa_deepseek_v4_greater_china_quality_v9.json
```

## 3. Scope Universe Contract

Scope-bearing questions now persist a structured contract containing:

```text
scope_id
scope_type
display_name
source
effective_date
membership_rule
entity_ids
size
scope_membership_hash
scope_eligibility_policy_hash
```

`scope_type` distinguishes an authoritative membership universe from a
dataset-defined complete-case universe. The latter is rendered explicitly as
the complete-case set of comparable entities satisfying the required inputs; it
is never presented as the entire real-world industry.

The new `scope_contract_integrity` quality check fails closed on:

```text
missing required fields
duplicate or empty members
member count mismatch
expected entity-set mismatch
membership hash mismatch
scope identity mismatch
eligibility policy hash mismatch
```

The Grounded Judge receives this contract directly, so scope quality is no
longer inferred from a short prose fragment alone.

## 4. Quality Evaluation Changes

The required-check manifest is upgraded to `qa_required_checks.v2` and requires
`scope_contract_integrity`. The evaluator uses role-specific fatal permissions:
the Surface Judge cannot claim missing grounded evidence, while the Grounded
Judge retains that authority. Each judge view also pins an evaluation reference
date so a completed fiscal period is not rejected merely for being recent.

T2 guidance now distinguishes a useful historical lookup from a genuinely
low-value trivial question. A question is not marked `overly_trivial` merely
because it has no multi-step arithmetic.

Feedback for formulaic output language now points to the correct component:
move machine formatting requirements into the hidden answer schema instead of
adding more surface suffix variants.

## 5. Distribution Selection and Readiness

The selector now targets answer types in addition to market, task, language,
and generation pipeline. Numeric answers target 42%; table, screening,
provenance, and follow-up answers receive explicit quotas.

Release readiness is fail-closed. A release is not training ready when any of
the following holds:

```text
numeric share is outside 35%-45%
market deviation exceeds 5 percentage points
accepted or accepted-for-coverage rate is below 80%
manual-review samples remain
```

## 6. Feedback Closure Gate

Feedback is closed through a cost-gated sequence:

```text
L2 issue hotspot
-> owning generator component
-> deterministic code or policy change
-> candidate-only regression
-> controlled rewrite canary
-> L0 and L2 re-evaluation
-> scale decision
```

Candidate-only validation is intentionally free of external model calls. A
large rewrite or release is permitted only after the canary meets all of these
conditions:

```text
controlled rewrite pass rate >= 97%
L0 required-check pass rate = 100%
L2 accepted or accepted-for-coverage rate >= 80%
confirmed formulaic, scope, and time issue rates < 5%
confirmed fatal count = 0
```

Configured token-price estimates are telemetry only and are not treated as
billing truth. Reports publish API calls and token counts as the authoritative
usage measures.
