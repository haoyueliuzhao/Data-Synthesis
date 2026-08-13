# Finance v25.17-v25.18 Runtime Resolution and Information Report

## 1. Scope

This report records the transition from the v25.12-v25.16 Runtime calibration series to a
fresh, capability-measurement-safe Flash experiment. It binds three distinct questions:

1. Does every rollout produce a complete, replayable, attributed terminal artifact?
2. Conditional on a valid Runtime measurement, where does Flash succeed or fail?
3. Do those outcomes span a sufficiently well-conditioned capability information matrix?

The central protocol rule is:

> Model correctness is a capability outcome. It is not a Runtime qualification gate.

No Pro call, Beneficiary screen, Objective access, Exact Target, GP-C evaluation, VTDO update, or
production Contribution was authorized in this experiment.

## 2. Protocol correction

The Runtime v2 contract separates four instrument gates from capability outcomes:

- execution integrity;
- terminal resolution;
- Runtime pathology;
- failure-attribution coverage.

Only L0-L2 failures are excluded from the model-capability denominator. Model protocol,
planning, recovery, stopping, verification, and semantic failures remain in
`P(Y=1 | R=1)`. Reports also preserve end-to-end `P(Y=1)`.

The v25.17 Development and Held-out artifacts remain immutable. They are not reclassified after
the fact. Their v1 policy used Semantic Accuracy in a non-saturation gate and therefore could not
support a downstream transition. Their useful descriptive results were:

| Slice | Semantic | Valid | Boundary cells |
|---|---:|---:|---:|
| v25.17 Development | 72.62% | 65.48% | 30.95% |
| v25.17 Held-out | 91.67% | 80.95% | 28.57% |

Runtime Resolution v2 instead uses Valid Success for capability non-saturation and has an explicit
`capability_support_redesign_only` route when the instrument passes but responses saturate.

## 3. Fresh task support

An initial history-disjoint 260-task source attempt produced 250 accepted tasks and 782 states,
but the Hard branching family had only one eligible task. Capability Frontier compilation stopped
fail-closed. No structural threshold was weakened.

The final offline source pool was rebuilt with a new seed. API freshness is enforced at final task
selection rather than by unnecessarily exhausting the offline source archive.

| Item | Result |
|---|---:|
| Requested source tasks | 420 |
| Attempted source tasks | 443 |
| Accepted source tasks | 420 |
| Accepted states | 1,394 |
| Source population status | passed |

The Capability Frontier then selected 70 tasks over seven capability families:

- 21 Easy Controls;
- 35 Frontier tasks;
- 14 Hard Controls.

All twelve structural dimensions were strictly monotonic. All seven family-primary-axis checks
passed. The structural capability matrix had numerical rank 7, full effective rank 5.413, and an
identifiable-subspace condition number of 4.453.

## 4. Public-contract regression

The public-contract audit was upgraded from an implicit three-Runtime assumption to an explicit,
frozen Runtime-arm set. The v25.18 regression is Flash-only and contains Scripted and Autonomous
Workflow Runtime arms. Direct and Pro are absent by contract.

Freshness is enforced at three levels:

- normalized task signature;
- Evidence ID;
- Evidence Version ID.

The contract excluded 133 prior task signatures and 371 prior Evidence/Version identities. It
selected seven fresh tasks and fourteen fresh Evidence/Version identities.

| Regression metric | Result |
|---|---:|
| Requested/recorded rollouts | 28/28 |
| Static public contracts | 14/14 passed |
| Technical resolution | 28/28 |
| Selector contradictions | 0 |
| Scripted selection-precondition failures | 0 |
| Deterministic contract defects | 0 |
| Model-side protocol violations | 1 |
| Semantic successes | 12/28 |

The semantic result is descriptive only. It did not affect Runtime qualification.

## 5. Runtime Resolution v2

Development and Held-out each used 21 tasks, two Workflow Runtimes, and two replicas. The Held-out
contract is disjoint from Development in group, semantic signature, source task, Evidence,
Evidence Version, and trajectory seed.

| Metric | Development | Fresh Held-out |
|---|---:|---:|
| Recorded rollouts | 84/84 | 84/84 |
| Execution integrity | 100% | 100% |
| Terminal resolution | 100% | 100% |
| Observation replay | 100% | 100% |
| Authority integrity | 100% | 100% |
| Failure attribution | 100% | 100% |
| Runtime-eligible denominator | 84 | 84 |
| Semantic accuracy given Runtime eligibility | 78.57% | 77.38% |
| Valid success given Runtime eligibility | 76.19% | 73.81% |
| Boundary-cell fraction | 28.57% | 23.81% |
| Scripted valid success | 85.71% | 83.33% |
| Autonomous valid success | 66.67% | 64.29% |

Held-out tier outcomes were 85.71% Easy, 67.86% Frontier, and 67.86% Hard. The result preserves a
real capability gradient without converting model failures into Runtime defects.

Held-out failures were fully attributed: 19 L4 Agent-decision failures, 3 L5 semantic failures,
and 62 L6 successes. No L0-L2 failure occurred.

The Held-out report therefore authorized only `flash_information_matrix_evaluation`.

## 6. Flash information matrices

The new information evaluator consumes Runtime Resolution v2 directly. It conditions outcomes on
Runtime eligibility and computes:

- a primary Final Valid matrix;
- seven non-authorizing axis-specific matrices;
- an equal-observed-axis joint capability matrix.

Demand vectors are L2-normalized and residualized against general difficulty for the axis
diagnostic. The source report and all 84 terminal outcomes are independently replayed before matrix
construction. Bootstrap intervals use 400 family-stratified task/realization resamples.

The first v1 matrix report exposed a floating-point pseudo-rank for a two-task Recovery slice whose
residual eigenvalues were approximately `1e-34`. That report remains immutable and non-authorizing.
The v2 numerical contract combines absolute (`1e-12`) and relative (`1e-6`) rank tolerances.

### Final and joint results

| Runtime | Final p | Boundary | Final rank | Final erank | Final cond. | Max family | Joint rank | Joint erank | Joint cond. | Ready |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Scripted | 0.8333 | 0.1429 | 3 | 2.0000 | 10.13 | 0.7339 | 5 | 1.5710 | 237,575.79 | no |
| Autonomous | 0.6429 | 0.3333 | 7 | 3.0835 | 135.21 | 0.4489 | 7 | 3.6236 | 167.80 | no |

The exact v2 JSON report is the authority for unrounded values.

### Axis-specific diagnosis

| Runtime | Retrieval | Planning | Calculation | Reconciliation | Verification | Recovery | Stopping |
|---|---:|---:|---:|---:|---:|---:|---:|
| Scripted success | 1.000 | n/a | 0.976 | 0.976 | 0.833 | 0.500 (5 tasks) | n/a |
| Autonomous success | 1.000 | 0.643 | 1.000 | 0.000 | 0.714 | 0.250 (2 tasks) | 0.714 |

Retrieval and Calculation are saturated, Autonomous Reconciliation is at the floor, and Recovery
has too few opportunity-bearing tasks. Both Runtime cells have zero informative axes under the
preregistered confidence-interval lower-bound rule. The observed capability vector is therefore
complete but not statistically balanced.

## 7. Decision

The final immutable decision is:

```text
runtime_qualification_passed = true
capability_measurement_suitable = true
information_matrix_ready = false
pro_sparse_anchor_authorized = false
next_permitted_stage = capability_task_support_redesign_only
```

The result is not a Runtime failure and not a negative Pro result. It says the fresh Flash task
support is capable of measuring success and failure, but the resulting information geometry is too
ill-conditioned and too concentrated to authorize the next causal stage.

The next task population must add independent groups and repeated realizations that:

1. move Scripted Final Valid boundary mass above 25%;
2. reduce Scripted family dominance below 60%;
3. add Recovery opportunities across all seven families;
4. move Retrieval, Calculation, and Reconciliation away from floor/ceiling saturation;
5. reduce Autonomous Final and joint condition numbers below 100;
6. produce positive bootstrap lower bounds on the required number of visible axes.

Selecting tasks using these Held-out outcomes and evaluating them on the same outcomes is
forbidden. A new Development selection policy and a separately fresh confirmation population are
required.

## 8. Cost and immutable artifacts

The v25.18 online stages made 2,130 API calls, used 10,757,609 provider-reported tokens, and recorded
an estimated cost of USD 1.3286557872. No Pro call or local GPU job occurred.

Primary artifacts are under `artifacts/vtdo_experiment/`:

- `finance_v25_18_agent_source_population420_v2_20260813/`;
- `finance_v25_18_capability_frontier_v2_20260813/`;
- `finance_v25_18_public_contract_regression_v1_20260813/`;
- `finance_v25_18_multitier_population_v2_20260813/`;
- `finance_v25_18_runtime_development_v2_20260813/`;
- `finance_v25_18_runtime_heldout_v2_20260813/`;
- `finance_v25_18_flash_information_v2_20260813/`.

The reports make no Contribution, training-utility, or downstream benchmark claim.
