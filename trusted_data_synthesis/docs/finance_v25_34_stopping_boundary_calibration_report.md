# Finance v25.34 Stopping Boundary Calibration Report

## Scope

v25.33 passed the common Top-4 geometry but failed its frozen parent-support contract because
State-dependent Stopping supplied only 3.16% of information, one nonzero task, and a zero
bootstrap lower bound. Failure-artifact replay then separated two possible causes:

1. `uncertain_source_coverage` contained an unreachable Host path: the Agent was asked to open a
   locator that had not necessarily been discovered by `search_archive`.
2. `unresolved_conflict_cannot_stop` returned typed conflict dimensions and three public
   resolution actions, but the generic failed-action Prompt discarded those fields before the
   next model decision.

v25.34 is a diagnostic measurement-instrument experiment. It does not reclassify v25.33 and does
not evaluate stable support, Pro anchors, a Beneficiary, Exact Target, GP-C, or Contribution.

## Frozen Design

- One fresh 20-task financial Population excluded all 29 prior submechanism Populations.
- The calibration selected its five State-dependent Stopping tasks.
- Each task received 12 independent `deepseek-v4-flash` realizations.
- The fixed denominator was 5 tasks / 60 rollouts.
- The primary response remained `capability_contract_success`:
  semantic validity AND ordered Host trigger/resolution behavior AND no post-completion violation.
- The first and second runs used the same tasks, model contract, Archive, and Runtime limits.
  Only the content-hashed implementation changed, making the comparison paired.

The pre-registered transition was deliberately narrow: a passing result permits only construction
of three new, mutually disjoint stable-support Development Populations.

## Instrument Repairs

### Source coverage

The Host now permits the public sequence:

```text
typed incomplete-source trigger
-> search_archive
-> open_document
-> cross_check_evidence
```

The static replay begins without a previously discovered locator, so a regression cannot be hidden
by scripted setup.

### Typed failed-action memory

The generic Agent Runtime now carries the following public fields into the next decision:

```text
observed_conflict_dimensions
available_resolution_actions
resolution_decision_rule
required_next_tools
```

If the Agent repeats a failed call and the Host blocks it, the Runtime preserves the most recent
typed prerequisite contract rather than replacing it with a generic argument-patch message. The
Prompt still does not identify the correct action. It asks the model to match each action's public
`applicable_when` condition to the observed public conflict dimensions.

## Paired Results

| Metric | v25.34-v1 | v25.34-v2 |
| --- | ---: | ---: |
| Requested / recorded | 60 / 60 | 60 / 60 |
| Runtime eligible | 60 | 60 |
| API transport | 100% | 100% |
| Bounded JSON | 100% | 100% |
| Observation replay | 100% | 100% |
| Authority integrity | 100% | 100% |
| Runtime pathology | 0% | 0% |
| Semantic accuracy | 80.00% | 96.67% |
| End-to-end valid | 80.00% | 93.33% |
| Locator precondition failures | 0 | 0 |
| Repair-target boundary tasks | 0 | 1 |

The three stopping controls remained 12/12 in both runs.

| Repair target | v1 resolution | v1 contract | v2 resolution | v2 contract |
| --- | ---: | ---: | ---: | ---: |
| `uncertain_source_coverage` | 12/12 | 12/12 | 12/12 | 11/12 |
| `unresolved_conflict_cannot_stop` | 0/12 | 0/12 | 10/12 | 9/12 |

For `unresolved_conflict_cannot_stop`, the v2 Contract probability is 0.75 with a Wilson 95%
interval of `[0.4677, 0.9111]`. It is therefore a non-degenerate boundary response under the
frozen `[0.10, 0.90]` point-probability interval. The result demonstrates that the prior all-zero
cell was caused by missing typed retry context, while preserving residual model decision error.

## Cost

| Item | v1 | v2 | Total |
| --- | ---: | ---: | ---: |
| API calls | 434 | 434 | 868 |
| Provider-reported model tokens | 1,918,574 | 1,945,965 | 3,864,539 |
| Estimated cost | $0.217497 | $0.214055 | $0.431551 |

Both runs requested `deepseek-v4-flash`. Model discovery observed both available DeepSeek model
IDs, but no Pro completion was requested and `pro_api_call_count` remained zero.

## Formal Decision

v25.34-v1 remains a frozen failed diagnostic:

```text
runtime_measurement_ready = true
stopping_instrument_repair_validated = false
boundary_signal_observed = false
next_permitted_stage = stopping_instrument_redesign_only
```

v25.34-v2 passes every pre-registered Runtime, instrument, and boundary gate:

```text
runtime_measurement_ready = true
stopping_instrument_repair_validated = true
boundary_signal_observed = true
fresh_stable_support_development_permitted = true
historical_result_reclassified = false
pro_api_call_count = 0
beneficiary_screening_authorized = false
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = fresh_stable_support_development_population_build
```

This is not evidence that stable parent support now passes. That claim requires a new 3-population,
60-task, 480-rollout Development experiment over task, Evidence, Evidence Version, semantic
signature, and submechanism-instance disjointness.

## Immutable Artifacts

- Fresh Population:
  `finance_v25_34_stopping_boundary_calibration_population_v1_20260815`
- Pre-repair contract/run:
  `finance_v25_34_stopping_boundary_calibration_contract_v1_20260815` and
  `finance_v25_34_stopping_boundary_calibration_v1_20260815`
- Post-repair paired contract/run:
  `finance_v25_34_stopping_boundary_calibration_contract_v2_20260815` and
  `finance_v25_34_stopping_boundary_calibration_v2_20260815`

