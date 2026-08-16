# Finance v25.47 Context Sufficiency Development

Experiment date: 2026-08-17

## Decision

v25.47 completed the preregistered construct-validity repair authorized after v25.46. It replaced
the opaque contextual branch cue with one typed, action-neutral public relation state and one
shared decision policy. The static design passed all sufficiency, invariance, and leakage tests,
and the 384-rollout DeepSeek V4-Flash execution passed the recursive measurement contract.

The contextual mechanism did not pass:

```text
static construct validity                 = passed
recursive measurement instrument          = passed
Contextual Shape aggregate admission      = passed
branch-balanced first-action accuracy      = 0.34375
constant-action baseline                   = 0.50000
contextual policy gain                     = -0.15625
paired hierarchical bootstrap LCB95        = 0.171875
contextual mechanism fidelity              = failed
production Contribution                    = 0
```

This is now interpreted as a localized Flash capability result under sufficient public Context,
not as another invitation to help the model through the same grammar. The immutable scientific
decision therefore forbids same-grammar Prompt assistance, threshold relaxation, post-hoc task
deletion, additional Flash replicas, Pro calls, Beneficiary screening, Exact Target, and GP-C.

## Frozen Design

The formal population contains 48 fresh tasks and 384 Flash rollouts:

| Component | Count |
| --- | ---: |
| Contextual paired tasks | 8 |
| Matched counterfactual pairs | 4 |
| Frozen regression tasks | 40 |
| Tasks per Shape | 8 |
| Replicates per task | 8 |
| Total rollouts | 384 |

Each contextual branch exposes the same three actions, in the same order and with symmetric
descriptions:

```text
normalize_metric_unit_period
    transform selected entries to a common interpretive convention

open_document
    inspect authoritative provenance when trust remains unsettled

query_structured_fact
    obtain another archived entry through a revised selector
```

Both branches also receive the same action-neutral policy:

> Choose the action whose stated effect resolves the sole unresolved relation while preserving
> every aligned relation.

The only branch difference is the typed public relation state. One branch identifies a different
observation event and requires a revised selector; the other identifies the same event under a
different registered convention and requires normalization. No branch label or Oracle mismatch
name is exposed.

## Pre-API Construct Audit

All static gates passed before any model call:

| Gate | Result |
| --- | ---: |
| Complete task / pair capacity | 48 / 4 |
| Same core task | 1.000 |
| Same public corpus | 1.000 |
| Same Prompt bytes | 1.000 |
| Single Context change | 1.000 |
| Correct action flip | 1.000 |
| Deterministic branch replay | 1.000 |
| Unique publicly applicable action | 1.000 |
| Public Context sufficiency | 1.000 |
| Action-order invariance | 1.000 |
| Action-label invariance | 1.000 |
| Context removal becomes indeterminate | 1.000 |
| Context swap flips the action | 1.000 |
| Action-description symmetry | 1.000 |
| Lexical action leakage | 0 |
| Context/action lexical overlap | 0 |
| Opaque branch-label leakage | 0 |

The removal and swap mutations are especially important. They show that the answer cannot be
derived from a fixed action prior, while the public Context alone is sufficient to change the
correct action. This closes the construct-validity ambiguity left by v25.46.

## Runtime Result

All requested records remain in the capability denominator:

| Metric | Result |
| --- | ---: |
| Auditable records | 384 / 384 |
| Successful Agent outcomes | 226 |
| Fail-closed behavior outcomes | 158 |
| Full-valid trajectories | 220 |
| Recursive Host field violations | 0 |
| Recursive Host marker violations | 0 |
| Shape analysis authorized | yes |

The raw instrument passed before Shape or mechanism aggregation. No failed behavior outcome was
deleted or converted into an infrastructure failure.

The aggregate Shape results were:

| Shape | Stopping success | Task range | Admitted |
| --- | ---: | ---: | --- |
| `authority_coverage_gap` | 0.6719 | 0.7500 | yes |
| `contextual_resolution_choice` | 0.5469 | 0.7500 | yes |
| `partial_required_evidence` | 0.8125 | 0.3750 | yes |
| `single_dimension_conflict` | 0.5625 | 0.8750 | no |
| `verified_extra_call_cost` | 1.0000 | 0.0000 | yes |
| `verified_extra_call_error_risk` | 1.0000 | 0.0000 | yes |

`single_dimension_conflict` failed only its frozen between-task heterogeneity gate. This regression
is retained as part of the complete conjunction and is not used to reinterpret the contextual
mechanism result.

## Mechanism Estimands

The primary response is the first registered action after all prerequisites have been observed:

```text
Y_ctx = 1[first post-prerequisite action is correct]
```

A later repair cannot rescue an incorrect first action. The paired response is:

```text
Y_flip = 1[period branch correct AND definition branch correct]
```

The frozen thresholds and observations were:

| Metric | Threshold | Observed | Passed |
| --- | ---: | ---: | --- |
| Dual-correct consistency | >= 0.125 | 0.21875 | yes |
| Informative pairs | 4 / 4 | 3 / 4 | no |
| Maximum branch gap | <= 0.75 | 0.375 | yes |
| Branch-balanced first-action accuracy | >= 0.625 | 0.34375 | no |
| Contextual policy gain over constant baseline | >= 0.125 | -0.15625 | no |
| Hierarchical bootstrap LCB95 | > 0.50 | 0.171875 | no |

The paired hierarchical bootstrap used 10,000 preregistered draws with seed `20260847`, resampling
both pair identities and paired realization identities. It therefore does not treat 64 branch
rollouts as independent tasks.

Per-pair observations were:

| Structural stratum | Period correct | Definition correct | Dual correct | Informative |
| --- | ---: | ---: | ---: | --- |
| Definition reconciliation | 4 / 8 | 4 / 8 | 3 / 8 | yes |
| Calculation chain | 4 / 8 | 2 / 8 | 2 / 8 | yes |
| Retrieval join | 0 / 8 | 1 / 8 | 0 / 8 | no |
| Verification selection | 5 / 8 | 2 / 8 | 2 / 8 | yes |

Dual correctness alone exceeds its weak smoke threshold, but the policy estimator is below the
constant-action baseline and its lower confidence bound is far below 0.5. Aggregate Shape
admission cannot rescue this prospective mechanism failure.

## First-Action Diagnostic

The read-only diagnostic did not alter any gate:

| Branch | Expected action | First-action attempts | Correct |
| --- | --- | --- | ---: |
| Period | query | query 24, normalize 6, open 2 | 13 / 32 |
| Definition | normalize | normalize 9, query 20, none 3 | 9 / 32 |

The Agent retained a strong query prior in the definition branch even though the public relation
state uniquely required normalization. The mechanism failure is therefore not explained by an
unobservable branch distinction, asymmetric action wording, Host contamination, or missing public
information.

## API Accounting

The run used only the exact requested `deepseek-v4-flash` identity:

| Item | Count |
| --- | ---: |
| Model interactions | 3,989 |
| HTTP successes | 3,989 |
| JSON-contract successes | 3,982 |
| Fallbacks | 0 |
| Prompt tokens | 21,184,412 |
| Prompt cache-hit tokens | 6,521,984 |
| Prompt cache-miss tokens | 14,662,428 |
| Completion tokens | 572,683 |
| Total provider-reported tokens | 21,757,095 |
| Frozen-price estimated cost | USD 2.2313527152 |

The cost is telemetry-based and is not presented as the user's cumulative billing total.

## Scientific Interpretation

v25.47 separates three claims that earlier revisions had partially conflated:

1. The public counterfactual construction is identifiable. This passed static removal, swap,
   order, label, symmetry, replay, and leakage tests.
2. The recursive Runtime is a valid measurement instrument. It passed all raw integrity gates.
3. Flash does not reliably use the sufficient Context to choose the correct first action under
   this frozen grammar. This failed the prospective mechanism estimator.

The result does not refute VTDO or prove that contextual tool selection is universally absent. It
does establish a local capability limitation for this model, population, Runtime, and estimand. A
new scientific question may use a genuinely different mechanism or model identity, but repeating
the same grammar with additional hints would no longer be an independent capability test.

## Governance Decision

The automatic report inherited the v25.46 transition label `contextual_shape_redesign_only`. A
separate immutable decision artifact applies the stricter pre-outcome rule and only removes
permissions:

```text
automated transition        = contextual_shape_redesign_only
governance transition       = contextual_tool_selection_limitation_recorded
same-grammar Prompt help    = forbidden
threshold relaxation        = forbidden
post-hoc task deletion      = forbidden
additional Flash rollouts   = forbidden
Pro / Beneficiary           = blocked
Exact Target / GP-C         = blocked
production Contribution     = 0
```

The frozen execution report is not mutated or reclassified.

## Reproducibility

Formal artifacts are under:

```text
finance_v25_47_context_sufficiency_protocol_20260817
finance_v25_47_context_sufficiency_population_20260817
finance_v25_47_context_sufficiency_execution_contract_20260817
finance_v25_47_context_sufficiency_development_20260817
```

The Development directory contains the raw records, outcomes, recursive audit, Shape report,
mechanism report, immutable final report, manifest, read-only diagnostic, and conservative
scientific decision. A deterministic no-API finalizer reproduced the frozen report identity after
the live execution.
