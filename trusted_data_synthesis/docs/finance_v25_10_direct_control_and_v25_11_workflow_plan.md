# Finance v25.10 Direct Control And v25.11 Workflow Plan

## Decision

The v25.8 audit identified two deterministic public-contract defects and a
task-instance confound. The follow-up work repaired those defects, ran an
independent fresh regression, constructed matched ladder groups, and evaluated
a Direct-only structural ladder with real DeepSeek Pro and Flash calls.

The resulting scientific decision is:

```text
Public-contract execution: repaired and independently regressed
Direct Runtime: positive execution control, not a capability-boundary arm
Scripted/Autonomous Runtime: the only arms eligible for workflow localization
Pro/Flash ranking: forbidden
Paired calibration: forbidden until the workflow information gate passes
Exact Target / GP-C / VTDO update: not evaluated and not authorized
```

This decision replaces the earlier assumption that Direct, Scripted, and
Autonomous should contribute equally to one capability information matrix.

## 1. Independent Public-contract Regression

The first v25.10 run was retained as an immutable diagnostic because it used
the pre-correction failure taxonomy. A second run used new public-task
semantics, excluded 105 previously exposed signatures, and classified failures
by causal layer.

Frozen v25.10 regression v2:

| Metric | Result |
| --- | ---: |
| Requested / recorded rollouts | 84 / 84 |
| Technical resolution | 84 / 84 |
| Deterministic compiler or verifier defects | 0 |
| Model protocol violations | 16 |
| Direct semantic successes | 28 / 28 |
| Scripted semantic successes | 6 / 28 |
| Autonomous semantic successes | 4 / 28 |
| API calls | 449 |
| Model tokens | 1,359,180 |
| Exact recorded cost | USD 0.3165810698 |

The 16 protocol violations comprise four malformed operation-reference
decisions and twelve Autonomous evidence-selection decisions. They are model
outputs that violated a satisfiable public contract; they are not reclassified
as compiler defects.

The passing report is
`finance_public_contract_regression_report:f266cbe0acb6d5e55b6344e90fd52e6de5b0878868af28ea8050885aa4c7527c`.
It authorizes matched-ladder construction only.

## 2. Static Structural Ladder

The Direct structural ladder separates operation/evidence complexity from
workflow decisions. It contains five families:

- branching operation plans;
- multi-hop retrieval joins;
- calculation chains;
- definition reconciliation;
- verification-sensitive selection.

Each family contains three independent ladder groups and three nested tiers.
The 45 tasks satisfy all static contracts:

| Static property | Result |
| --- | ---: |
| Groups / tasks | 15 / 45 |
| Public-contract records | 45 |
| Public-contract pass rate | 100% |
| Nested Gold evidence | 100% |
| Operation-depth monotonicity | 100% |
| Evidence-reference coverage | 100% |
| Program replay | 100% |
| Public corpus equals Gold evidence | 100% |

The frozen population is
`finance_structural_capability_ladder_population:5a93faa6152a3f368584cb7d08b4c14d8b358395bc535e9ec485d90f75bd9cab`.

## 3. Real Direct Control Result

The structural ladder was executed with both DeepSeek models:

```text
45 tasks x 2 models x 5 replicas = 450 rollouts
```

| Metric | Result |
| --- | ---: |
| Completed / requested | 450 / 450 |
| Technical resolution | 100% |
| Raw and bounded JSON resolution | 450 / 450 |
| Observation replay | 450 / 450 |
| Authority integrity | 450 / 450 |
| Budget / infrastructure failures | 0 / 0 |
| Semantic success | 449 / 450 (99.7778%) |
| Pro semantic success | 224 / 225 |
| Flash semantic success | 225 / 225 |
| Monotone grouped ladders | 29 / 30 (96.6667%) |
| API calls | 900 |
| Model tokens | 7,022,963 |
| Exact recorded cost | USD 0.9620609844 |

Every Model x Family x Tier cell achieved 15/15 except Pro Calculation
Frontier, which achieved 14/15. No family had an informative non-saturated
tier.

This is not evidence that structural complexity is irrelevant. In Direct
`PLAN_GIVEN`, the public Program Skeleton fixes the operation graph, Host code
executes the semantic operations, and the final-answer prompt exposes the
verified answer-result seed. Increasing evidence count and operation depth
therefore increases a controlled execution/copying burden without preserving
the corresponding planning, retrieval, calculation, or verification decision.

Consequently, Direct is now frozen as:

```text
positive_execution_control
```

It verifies public-schema exposure, deterministic Host execution, answer
projection, and model-visible result emission. It is excluded from empirical
capability boundary selection, the response-weighted information matrix, and
paired calibration authorization.

The original v1 report remains immutable. The code-level v2 report contract
reinterprets future Direct runs as positive controls and cannot emit a Direct
capability-tier selection.

## 4. Workflow Development Evidence

The prior matched v25.9 run remains a development diagnostic:

| Metric | Result |
| --- | ---: |
| Rollouts | 1,890 / 1,890 |
| API calls | 11,516 |
| Model tokens | 42,889,747 |
| Exact recorded cost | USD 7.6765978432 |
| Grouped monotonic ladders | 97 / 126 (76.9841%) |
| Scripted families with a selected tier | 4 / 7 |
| Autonomous families with a selected tier | 3 / 7 |

It showed useful workflow signal in definition reconciliation, verification,
recovery, stopping, and multi-hop retrieval. It also showed floor behavior in
branching and calculation and residual model-side operation-reference or
evidence-selection violations. Because this population predates the final
freshness exclusions and treated Direct as a peer Runtime, it is not a formal
calibration population.

## 5. Freshness And Capacity

A first attempt to construct another seven-family regression correctly failed
before API access because the 70-task frontier pool had no semantically fresh
Easy multi-hop task. The freshness contract was not weakened.

The matched-ladder builder was instead extended to consume multiple immutable
exposure contracts. It excludes both the independent regression tasks and all
45 Direct-control tasks by normalized core semantic signature. A larger real
Finance evidence pool then produced a new workflow ladder:

| Property | Result |
| --- | ---: |
| Ladder groups | 21 |
| Task variants | 63 |
| Static Task x Runtime checks | 189 / 189 |
| Fresh normalized core semantics | yes |
| Cross-group Gold/corpus disjointness | yes |
| Model API calls during construction | 0 |

The population is
`finance_matched_capability_ladder_population:bdcec79ef41252e10dc2ba2bb2bde0b3a0a4f67e7e437f926a1f0d049c725884`.

## 6. Workflow-only v2 Contract

The v2 localization contract removes Direct rather than retaining it for
historical compatibility. Its immutable denominator is:

```text
63 tasks x 2 workflow runtimes x 2 models x 5 replicas = 1,260 rollouts
```

The workflow Runtimes are exactly:

```text
scripted_tool
autonomous_agent
```

The frozen contract has 126 Runtime bindings and identity
`finance_matched_tier_localization_contract:6c079e1a9a9d0c18749b972897c1241d85fb2731f898954bfdcf753fb72e2918`.
It is stored under
`artifacts/vtdo_experiment/finance_v25_11_workflow_localization_contract_v1_20260813`.

The v25.10 regression originally referenced a temporary worktree path. Its
5.35 MB population is now mirrored under
`artifacts/frozen_inputs/sha256/eb73d14f560255244a8e7251aa506c83e043b9e82b9769f0242fcfeb068e00ce`.
Replay prefers the unchanged original and permits this mirror only when the
original is absent and the mirror content matches the frozen digest. A changed
original can never fall back to the mirror.

The v2 report cannot proceed to an information audit unless both workflow
Runtimes satisfy their pre-registered family threshold and the grouped
monotonicity gate. Autonomous Bridge remains a fail-closed outcome when Easy
is still a response floor.

## 7. Cost-aware Next Execution

The next real API stage is the frozen 1,260-rollout workflow experiment. It
must use checkpointed parallel execution and exact provider telemetry. The
following rules apply:

1. resume by immutable `(model, binding, replica)` identity;
2. never add Direct records to fill a weak workflow cell;
3. report every Model x Runtime x Family x Tier denominator;
4. preserve model protocol failures rather than repairing them into success;
5. do not select a Tier from an aggregate rate without at least two
   informative matched groups;
6. run the empirical capability information audit only when the workflow
   localization report explicitly authorizes it;
7. do not access Validation or Authorization Objective data in this stage.

No further expensive Direct ladder is justified. If the workflow experiment
again places a family entirely at floor or ceiling, the next action is a
Runtime-specific Bridge or task redesign, not threshold relaxation.

## Claim Boundary

The completed work supports these claims:

1. the v25.8 deterministic public-contract defects have been repaired;
2. an independent 84-rollout regression found no deterministic contract
   defect;
3. Direct is a stable positive execution control under the current Runtime;
4. a fresh, statically satisfiable workflow ladder is available;
5. the next workflow experiment has a complete immutable denominator.

It does not support a Pro/Flash capability ranking, Explorer selection,
Beneficiary frontier, Exact Target result, GP-C authorization, Contribution
estimate, or VTDO distribution update.

## Implementation Verification

The independently passing regression and Direct control together used 1,349
API calls, 8,382,143 model tokens, and USD 1.2786420542. The earlier v25.10 v1
taxonomy diagnostic and v25.9 development run are not included in that subtotal.
Building the v25.11 population and contract used no model API calls.

Final repository verification on 2026-08-13:

```text
Ruff: passed
Mypy: 275 source files passed
Pytest: 534 passed in 137.13 seconds
git diff --check: passed
workflow contract replay: 126 bindings, 1,260 rollouts,
                          Scripted/Autonomous only
```
