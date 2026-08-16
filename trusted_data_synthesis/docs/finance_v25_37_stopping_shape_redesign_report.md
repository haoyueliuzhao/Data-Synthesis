# Finance v25.37 Stopping Shape Redesign Development

## Decision

v25.37 implements the only next experiment authorized by v25.36. It keeps the three
previously passing Shapes unchanged on fresh tasks, redesigns only the three failed
Shapes, and doubles the independent-task denominator without increasing realizations
per task.

All 384 DeepSeek V4-Flash rollouts over 48 fresh Finance tasks completed. Every Runtime
measurement gate passed, but none of the three redesigned Shapes was admitted and one
frozen positive control regressed:

~~~
runtime_measurement_ready = true
positive_control_regression_count = 1
redesigned_shape_admission_count = 0
all_shapes_admitted = false
difficulty_policy_frozen = false
fresh_three_population_preparation_authorized = false
pro_api_call_count = 0
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = stopping_shape_redesign_only
~~~

This is a negative Shape-support result. It is not a Runtime failure, a GP-C result, a
Contribution result, or evidence against the theoretical existence of Stopping
capability.

## Preregistered Design

The immutable population contains six Shapes, four structural strata per Shape, two
independently materialized tasks per Shape-stratum cell, eight independent tasks per
Shape, and eight realizations per task. The total denominator is 48 tasks and 384
rollouts. The model contract is Flash-only.

The frozen positive controls are authority coverage gap, contextual resolution choice,
and verified extra-call error risk. The failed Shapes received these changes:

1. Partial required evidence exposes only required, resolved, and missing role counts
   plus a public completeness rule; it does not disclose the missing role identity.
2. Single-dimensional conflict exposes one conflict dimension and two typed actions
   with applicability conditions. The matching action resolves the conflict in one step
   while a distractor remains available.
3. Verified extra-call cost exposes a standardized relative cost equal to 25% of
   remaining call budget, 20% of remaining token budget, and a terminal utility loss
   of 1.0.

Static construction passed before API access:

| Static gate | Result |
| --- | --- |
| Shape x stratum task cells | 24/24 have exactly 2 tasks |
| Operation replay | 100% |
| Host replay | 100% |
| Public/Oracle isolation | 100% |
| Answer contract | 100% |
| Public decision contract | 100% |
| Within-population Evidence disjointness | pass |
| Historical task and Evidence disjointness | pass |
| Historical semantic and materializer disjointness | pass |
| Positive controls unchanged | pass |
| Failed Shapes only redesigned | pass |

Candidate-Shape admission requires:

~~~
complete independent task denominator = 8/8
boundary probability interval = [0.125, 0.875]
boundary tasks >= 4
nonzero-information tasks >= 6
effective task count >= 4.0
maximum single-task information share <= 0.35
between-task probability range <= 0.75
hierarchical bootstrap information LCB > 0
~~~

Controls require mean Capability Contract success of at least 0.75 and the same
heterogeneity bound. The bootstrap samples task first and realization second. Pooled
rescue, task deletion, task selection, threshold changes, and historical
reclassification are forbidden.

## Runtime Result

| Measure | Result |
| --- | ---: |
| Recorded denominator | 384/384 |
| Execution integrity | 100% |
| Terminal resolution | 100% |
| API transport resolution | 100% |
| Bounded JSON resolution | 100% |
| Observation replay | 100% |
| Authority integrity | 100% |
| Runtime pathology | 0% |
| L0-L2 failures | 0 |
| Behavior success | 84.90% |
| Primary valid success | 63.02% |
| Capability Contract success | 63.02% |

The Runtime instrument is usable. Incorrect model decisions remain capability
observations rather than being relabeled as Runtime failures.

## Shape Result

| Shape | Status | Mean | Boundary | Nonzero | Effective | Max share | LCB | Range | Admit |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| authority_coverage_gap | frozen positive | 0.5156 | 8 | 8 | 7.884 | 0.147 | 1.0781 | 0.500 | yes |
| contextual_resolution_choice | frozen positive | 0.2969 | 6 | 6 | 5.724 | 0.205 | 0.4219 | 0.750 | yes |
| partial_required_evidence | redesigned | 0.8906 | 2 | 2 | 1.870 | 0.632 | 0.0000 | 0.750 | no |
| single_dimension_conflict | redesigned | 0.8281 | 4 | 4 | 3.689 | 0.314 | 0.1875 | 0.500 | no |
| verified_extra_call_cost | redesigned | 0.5313 | 4 | 4 | 3.765 | 0.326 | 0.1094 | 1.000 | no |
| verified_extra_call_error_risk | frozen positive | 0.7188 | 6 | 6 | 5.692 | 0.216 | 0.4688 | 0.750 | no |

### Structural-stratum response

| Shape | Retrieval | Calculation | Definition | Verification |
| --- | ---: | ---: | ---: | ---: |
| authority_coverage_gap | 0.3125 | 0.6250 | 0.6250 | 0.5000 |
| contextual_resolution_choice | 0.1250 | 0.4375 | 0.2500 | 0.3750 |
| partial_required_evidence | 0.9375 | 1.0000 | 0.6250 | 1.0000 |
| single_dimension_conflict | 0.9375 | 0.7500 | 0.7500 | 0.8750 |
| verified_extra_call_cost | 0.4375 | 0.6250 | 0.1875 | 0.8750 |
| verified_extra_call_error_risk | 0.5000 | 0.8125 | 0.8125 | 0.7500 |

Each cell contains two tasks and sixteen realizations. These means are diagnostics and
were not pooled to change Shape admission.

## Interpretation

### Partial evidence remains too easy

Six of eight tasks were saturated at 8/8 and only two tasks carried nonzero
information. Count-only disclosure removed direct missing-role leakage, but did not
make the completion decision consistently difficult. The next design must alter the
evidence dependency, not merely the state wording.

### Conflict moved from floor to ceiling

The one-step, two-action redesign moved mean success from the v25.36 floor to 0.8281.
This is calibration progress, but only four tasks remained non-saturated. A future
design should keep one-step resolution while removing the direct lexical match between
the observed dimension and the applicable action.

### Relative cost is still not comparable

The standardized public cost did not stabilize response. Stratum success ranged from
0.1875 to 0.875, while task success covered the full zero-to-one interval.

### One positive control did not replicate

Verified extra-call error risk scored 0.7188, below the frozen 0.75 threshold. It cannot
be treated as permanently stable based only on v25.36.

## Primary-response Diagnostic

Both post-completion controls had 100% ordered Host behavior and resolution in every
stratum, while Capability Contract success was 0.5313 for cost and 0.7188 for error
risk. The frozen primary response is the conjunction of valid final answer and ordered
Host behavior. Unrelated answer difficulty can therefore affect a Stopping Control.

This diagnostic cannot rescue v25.37. Before another API run, the theory-to-estimand
mapping must prospectively decide whether a Control measures pure stopping behavior or
the complete valid-trajectory event.

## API And Artifact Accounting

- requested model: DeepSeek V4-Flash;
- discovered models: Flash and Pro;
- Pro calls: 0;
- Agent/Host API turns: 4,187;
- calls per rollout: median 11, p95 15, maximum 20;
- contract-repair calls: 3;
- Host verification repairs: 0;
- total model tokens: 21,901,900;
- configured price estimate: USD 2.044219.

The monetary value comes from frozen client-side pricing metadata and is not a provider
invoice. It must not be reported as billed cost without provider reconciliation.

Every immutable output hash verifies. Records, outcomes, terminal outcomes, and
behavior observations each contain exactly 384 rows.

## Permitted Next Work

No three-population Confirmation is authorized. Work is limited to model-free Shape and
estimand redesign:

1. freeze whether support targets decision behavior or full valid trajectory;
2. construct a genuinely nontrivial partial-evidence dependency;
3. retain one-dimensional, one-step conflict resolution but remove lexical answer
   matching;
4. implement a task-invariant realized cost, or withdraw cost as a control if that is
   impossible;
5. retain all positive controls as preregistered checks, not guaranteed passes;
6. build another fully fresh 6 x 4 x 2 task population only after static calibration;
7. continue to forbid Pro, Beneficiary, Exact Target, GP-C, Contribution, VTDO update,
   and Student training.

## Authoritative Artifacts

- artifacts/vtdo_experiment/finance_v25_37_stopping_shape_redesign_protocol_v1_20260816/
- artifacts/vtdo_experiment/finance_v25_37_stopping_shape_redesign_population_v1_20260816/
- artifacts/vtdo_experiment/finance_v25_37_stopping_shape_redesign_contract_v1_20260816/
- artifacts/vtdo_experiment/finance_v25_37_stopping_shape_redesign_development_v1_20260816/
