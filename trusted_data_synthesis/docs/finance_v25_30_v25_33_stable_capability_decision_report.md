# Finance v25.30-v25.33 Stable Capability-decision Report

## Scope

This report freezes the capability-support work completed after the v25.29 held-out failure.
The work does not estimate Exact Target, GP-C, or VTDO Contribution. It only asks whether fresh
Flash trajectories provide a stable, identifiable capability-decision response distribution.

The primary response is:

```text
capability_contract_success
= valid final answer
  AND ordered Host trigger/resolution behavior
  AND no post-completion violation
```

Answer correctness alone is diagnostic and cannot rescue the primary response.

## Measurement-contract Repair

The public task previously disclosed oracle mechanism identity and, in several cases, the exact
repair action. v25.32 replaced that interface with a neutral typed Host-state contract:

- public tasks no longer contain submechanism IDs, parent mechanism IDs, or intervention kinds;
- trigger and resolution events use neutral typed Host events;
- the LLM must choose the repair action from public state, tool schemas, and observations;
- canonical repair values remain Oracle-only;
- the final response requires both semantic validity and the registered behavior;
- missing provider token telemetry is a transient instrumentation error, retried independently
  from model-contract repair and retained in telemetry.

Every generated population now replays the positive branch, the wrong branch, Evidence
disjointness, and public mechanism non-disclosure before an API run is permitted.

## v25.32 Calibration

The first 60-rollout calibration exposed unreachable or mismatched behavior paths. After repairing
the public decision contract and Runtime, the second fresh calibration completed all 60 rollouts.

| Metric | v25.32 calibration v2 |
| --- | ---: |
| API / JSON / replay / authority | 100% |
| Runtime pathology | 0% |
| Semantic accuracy | 58.33% |
| Ordered behavior success | 58.33% |
| Capability-contract success | 43.33% |
| Residual numerical rank | 4 |
| Effective rank | 2.6149 |
| Condition number | 34.6669 |
| Informative axes | 7 / 7 |

The effective-rank threshold was 3.0, so this calibration remains a formal failure. It authorized
only a fresh 3-task-instance x 8-realization Development study; it did not authorize Confirmation
or Pro.

## v25.33 Frozen Design

The v25.33 protocol inherits the preregistered Top-4 stable-subspace policy and freezes:

- 20 typed submechanisms;
- three mutually disjoint real-Finance task instances per submechanism;
- eight Flash realizations per task;
- 60 tasks and 480 rollouts;
- disjoint task, Evidence, Evidence Version, semantic-signature, and materializer identities;
- `capability_contract_success` as the only primary response.

All three fresh populations passed static Host replay, wrong-branch rejection, Evidence
disjointness, and public non-disclosure. The immutable Development contract requested exactly
480 Flash rollouts.

## v25.33 Development Result

The run completed 480/480 rollouts with 24 workers.

| Runtime metric | Result |
| --- | ---: |
| API transport resolution | 100% |
| Bounded JSON resolution | 100% |
| Observation replay | 100% |
| Authority integrity | 100% |
| Runtime pathology | 0% |
| Semantic accuracy | 69.58% |
| End-to-end valid success | 61.67% |
| Host trigger observed | 99.58% |
| Host resolution observed | 70.00% |
| Ordered behavior success | 70.00% |
| Capability-contract success | 61.25% |

The run used 3,897 API calls, 18,490,956 model tokens, and the provider-aware cost estimator
recorded USD 1.9786909128.

### Stable Top-4 Geometry

| Geometry metric | Result | Gate |
| --- | ---: | ---: |
| Identifiable rank | 6 | >= 4 |
| Top-4 effective rank | 3.5929 | >= 3 |
| Top-4 condition number | 3.4290 | <= 100 |
| Boundary-task fraction | 56.67% | >= 25% |
| Nonzero-weight tasks | 34 | >= 12 |
| General-factor fraction | 16.47% | <= 85% |
| Informative axes | 7 / 7 | >= 4 |
| Bootstrap joint-geometry pass | 99.90% | >= 80% |

The common stable geometry therefore passed. This is a positive result: the repaired primary
response supports a well-conditioned Top-4 capability subspace on fresh tasks.

### Parent-support Failure

The study was still rejected because stable support was not distributed across every parent
mechanism.

| Parent mechanism | Information share | Nonzero tasks |
| --- | ---: | ---: |
| Candidate verification and repair | 24.74% | 9 |
| Cross-family failure recovery | 38.95% | 13 |
| State-dependent control and stopping | 3.16% | 1 |
| Typed tool plan and argument recovery | 33.16% | 11 |

Failed gates:

- minimum parent information share: 3.16% < 5%;
- minimum parent-share bootstrap LCB: 0% < 1%;
- minimum nonzero tasks per parent: 1 < 2.

Within Stopping, `incomplete_continue`, `post_complete_cost`, and
`post_complete_error_risk` were deterministic successes; `unresolved_conflict_cannot_stop`
was a deterministic failure; only `uncertain_source_coverage` contributed task-level variance.
This is not repaired by lowering the parent thresholds.

## Runtime Reachability Finding

Failure-artifact replay found a separate measurement-instrument defect in
`uncertain_source_coverage`:

1. an Agent can retrieve a public locator through `query_structured_fact` without first calling
   `search_archive`;
2. the Host then requires `open_document`;
3. `open_document` accepts only locators previously discovered through Archive search;
4. after the trigger, the registered resolution policy accepts only `open_document`.

This creates a state-dependent unreachable recovery path. It must be repaired and added to static
negative/positive replay before another Stopping calibration. The unresolved-conflict path is
different: its normalization action is available, but Flash did not select it in 24 attempts. That
path is currently too hard rather than mechanically unreachable.

## Frozen Decision

```text
v25_32_calibration_reclassified = false
v25_33_runtime_measurement_ready = true
v25_33_common_top4_geometry_passed = true
v25_33_capability_support_admitted = false
fresh_confirmation_authorized = false
pro_sparse_anchor_authorized = false
beneficiary_screening_authorized = false
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = stable_support_redesign_only
```

The next experiment must be a separately identified Stopping measurement repair and boundary
calibration. It may use fresh Development tasks, but it cannot reuse v25.33 as Confirmation,
relax the frozen parent gates, or access Pro/Beneficiary/Objective data.
