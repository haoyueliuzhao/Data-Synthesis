# Finance v25.36 Stopping Shape Stability Development

## Decision

v25.36 implements the shape-level Development requested by the v25.35 audit. It does
not pool the three v25.35 populations, increase replicas on the same task, reclassify a
historical result, or relax any stable-support threshold.

The run completed 192/192 DeepSeek V4-Flash rollouts over 24 fresh Finance tasks. The
Runtime measurement instrument passed every hard gate, but only three of the six
Stopping Shapes passed their preregistered task-level gates. Therefore:

```text
runtime_measurement_ready = true
all_shapes_admitted = false
difficulty_policy_frozen = false
fresh_cross_population_preparation_authorized = false
pro_api_call_count = 0
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = stopping_shape_support_redesign_only
```

This is a negative Shape-support result, not a Runtime failure, a GP-C result, or a
claim about theoretical Contribution.

## Design

The source-sensitivity audit first replayed v25.35 without new API calls. It rejected a
Stopping-only explanation for the cross-population geometry drift and found substantial
single-task sensitivity. The largest leave-one-task rotations were 48.53, 78.86, and
56.42 degrees across the three populations. This justified changing the primary
sampling unit from repeated realization to independent Finance task.

The Development population then froze:

- six Stopping Decision Shapes;
- four independent task instances per Shape;
- four structural strata per Shape: retrieval join, calculation chain, definition
  reconciliation, and verification-sensitive selection;
- eight realizations per task, for 192 total rollouts;
- a five-dimensional historical exclusion contract over task, Evidence, Evidence
  Version, semantic signature, and materializer identity;
- expected Host-event projections before any API call;
- a hierarchical task-and-realization bootstrap;
- no pooled rescue, post-hoc task selection, or historical reclassification.

Candidate Shapes had to satisfy all of the following:

```text
boundary tasks >= 2/4
nonzero-information tasks >= 3/4
effective task count >= 2.0
maximum single-task information share <= 0.60
between-task probability range <= 0.75
hierarchical bootstrap information LCB > 0
```

Runtime controls required mean Contract success of at least 0.75 and the same
between-task heterogeneity bound. Runtime execution, terminal resolution, Observation
replay, and authority integrity remained exact 100% gates, with zero Runtime pathology
and zero L0-L2 failures.

## Runtime Result

| Measure | Result |
| --- | ---: |
| Execution integrity | 100% |
| Terminal resolution | 100% |
| API transport resolution | 100% |
| Bounded JSON resolution | 100% |
| Observation replay | 100% |
| Authority integrity | 100% |
| Runtime pathology | 0% |
| L0-L2 failures | 0 |
| Behavior success | 67.19% |
| Capability Contract success | 52.08% |

The difference between Runtime integrity and Capability Contract success is intentional:
correctness is the measured Agent response, not a Runtime admission condition.

## Shape Result

| Shape | Role | Mean | Boundary tasks | Nonzero tasks | Effective tasks | Max task share | Bootstrap LCB | Range | Result |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `authority_coverage_gap` | candidate | 0.3125 | 3 | 3 | 2.970 | 0.357 | 0.1875 | 0.625 | pass |
| `contextual_resolution_choice` | candidate | 0.4063 | 4 | 4 | 3.725 | 0.340 | 0.2969 | 0.625 | pass |
| `partial_required_evidence` | candidate | 0.7813 | 3 | 3 | 2.604 | 0.517 | 0.0000 | 0.625 | fail |
| `single_dimension_conflict` | candidate | 0.0625 | 1 | 1 | 1.000 | 1.000 | 0.0000 | 0.250 | fail |
| `verified_extra_call_cost` | control | 0.7188 | 2 | 2 | 1.870 | 0.632 | 0.0000 | 0.875 | fail |
| `verified_extra_call_error_risk` | control | 0.8438 | 3 | 3 | 2.604 | 0.517 | 0.0000 | 0.375 | pass |

### Stable positive Shapes

`authority_coverage_gap` and `contextual_resolution_choice` both place at least three
independent tasks in a non-saturated region, retain effective task counts near three or
higher, and have positive hierarchical bootstrap lower bounds. They are valid design
prototypes for a future Development population. They are not independently published as
a Difficulty Policy because the policy is an all-Shape contract.

### Partial required evidence

Task success probabilities were 1.000, 0.875, 0.875, and 0.375 across the four strata.
Three tasks carried information, but hierarchical resampling still assigned nontrivial
mass to zero-information task compositions, producing an information LCB of zero. This
Shape is not rescued by its 78.13% mean or by its three nominal boundary tasks.

The next redesign must alter the structural consequence and evidence-dependency depth
for the Shape as a whole. It may not simply discard the saturated tasks after observing
their responses.

### Single-dimensional conflict

Three task strata had 0/8 Contract success and the remaining stratum had 2/8. All
observed information came from one task. This fails boundary count, nonzero-task count,
effective-task count, task-dominance, and bootstrap gates simultaneously.

The typed Runtime path was fully reachable and replayable, so the failure is a real
task-to-model response. A future design must reduce structural difficulty uniformly,
for example by freezing one explicit conflict dimension, a small set of publicly
applicable actions, and a shorter resolution chain without selecting the correct action.

### Additional-call cost control

Success probabilities were 1.000, 1.000, 0.750, and 0.125. The 0.875 task range and
71.88% mean fail both frozen control gates. The same nominal extra-call cost does not
currently define an equivalent control across Finance task strata. The error-risk
control did pass, showing that the general Stopping instrument remains operational.

## Scientific Interpretation

v25.36 validates the central recommendation from v25.35: task-level replication reveals
support failures that repeated realizations of a single task conceal. Two candidate
Shapes generalize across task strata, while three other Shapes remain structurally
miscalibrated. A pooled Shape result would obscure that distinction and is therefore not
computed for admission.

The result supports the following narrower statement:

> The repaired Stopping Runtime can measure task-conditioned stopping behavior, and two
> preregistered decision shapes exhibit stable boundary information across independent
> Finance tasks. The complete Stopping support policy is not yet stable enough to freeze.

It does not authorize Pro, Beneficiary screening, Exact Target, GP-C, Contribution,
VTDO updates, or Student training.

## Permitted Next Experiment

Only a new, separately identified Shape-redesign Development is permitted. It should:

1. retain the two passing Shapes as untouched positive controls on fresh tasks;
2. recalibrate `partial_required_evidence` across all four structural strata;
3. simplify `single_dimension_conflict` without leaking the correct resolution action;
4. redefine extra-call cost so that its consequence is comparable across task families;
5. freeze every structural change before API execution;
6. use new task, Evidence, Evidence Version, semantic-signature, and materializer IDs;
7. keep the same task-level bootstrap and no-pooling rule.

Only if every redesigned Shape passes Development may a Difficulty Policy be frozen and
a fresh three-population stable-support Confirmation be prepared.

## Accounting And Artifacts

- API calls: 2,049 Host/Agent turns across 192 rollouts;
- model tokens: 10,601,129;
- estimated API cost: USD 1.019713;
- requested model: `deepseek-v4-flash`;
- Pro model calls: 0;
- post-hoc Finalizer fix: false.

Authoritative artifacts:

- `artifacts/vtdo_experiment/finance_v25_36_stopping_shape_stability_protocol_v1_20260816/`
- `artifacts/vtdo_experiment/finance_v25_36_stopping_shape_population_v1_20260816/`
- `artifacts/vtdo_experiment/finance_v25_36_stopping_shape_stability_contract_v1_20260816/`
- `artifacts/vtdo_experiment/finance_v25_36_stopping_shape_stability_development_v1_20260816/`
