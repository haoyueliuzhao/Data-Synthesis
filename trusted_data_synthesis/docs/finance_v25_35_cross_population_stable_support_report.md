# Finance v25.35 Cross-population Stable-support Development

## Executive Decision

v25.35 completed the fresh three-population experiment authorized by v25.34:

```text
3 mutually disjoint populations
60 fresh Finance tasks
8 Flash realizations per task
480/480 completed rollouts
```

The Runtime-conditioned measurement instrument passed in all three populations, but stable
capability support did not. Only Population 2 passed every per-population support gate, and none of
the three pairwise Top-4 bootstrap alignments passed. The fail-closed decision is therefore:

```text
all_population_runtime_ready = true
all_population_capability_support_admitted = false
cross_population_alignment_ready = false
development_admitted = false
fresh_confirmation_preparation_authorized = false
next_permitted_stage = stable_support_redesign_only
```

This result does not evaluate Pro, Beneficiary, Exact Target, GP-C, or Contribution.

## Frozen Design

The protocol is descended from the positive v25.34-v2 stopping-instrument calibration, while
v25.33 remains a frozen failure. Before any API call, the experiment froze:

- all 30 historical capability-submechanism populations as exclusions;
- three sequentially generated fresh populations;
- disjointness on Task, Evidence, Evidence Version, semantic signature, and materializer instance;
- six Stopping decision shapes;
- exact per-population Runtime gates;
- a strict positive Stopping-parent bootstrap lower bound;
- at least two nonzero Stopping tasks per population;
- pairwise Top-4 principal-angle and bootstrap-alignment gates;
- a prohibition on pooled results rescuing a failed population.

All fresh tasks use `finance_capability_submechanism_scenario.v8` and
`finance_capability_submechanism_runtime.v10`.

## Runtime-conditioned Observability

Each population passed five destructive typed-context checks before API use:

1. removing observed conflict dimensions is rejected;
2. reversing the available-action order remains valid;
3. adding an unavailable distractor action is rejected;
4. an identical failed call cannot erase the latest typed prerequisite;
5. the Host exposes no correct parameters, Evidence IDs, canonical candidate, or hidden program.

The three fresh populations produced three distinct content-addressed action-order signatures.
During the real run, every population emitted and replayed the typed conflict context in all 8/8
registered conflict realizations. Populations 2 and 3 contained 2 and 12 identical-call blocks,
respectively; all 14 preserved the latest typed prerequisite. Population 1 had no identical block,
so its dynamic memory check was vacuous while the static destructive replay remained passing.

## Execution Integrity

All three populations independently achieved:

| Gate | Population 1 | Population 2 | Population 3 |
| --- | ---: | ---: | ---: |
| Rollout denominator | 160/160 | 160/160 | 160/160 |
| Execution integrity | 100% | 100% | 100% |
| Terminal resolution | 100% | 100% | 100% |
| Observation replay | 100% | 100% | 100% |
| Authority integrity | 100% | 100% | 100% |
| Runtime pathology | 0% | 0% | 0% |
| L0-L2 failures | 0 | 0 | 0 |
| Typed-context replay | 100% | 100% | 100% |

The run made 4,029 API calls, processed 19,773,005 model tokens, and recorded an estimated provider
cost of USD 2.16499. No Pro call was made.

## Per-population Geometry

| Metric | Population 1 | Population 2 | Population 3 | Requirement |
| --- | ---: | ---: | ---: | ---: |
| Boundary-task fraction | 65% | 70% | 60% | >=25% |
| Nonzero tasks | 13 | 14 | 12 | >=12 |
| Identifiable rank | 6 | 6 | 5 | >=4 |
| Top-4 effective rank | 3.310 | 3.654 | 3.383 | >=3 |
| Top-4 condition number | 5.106 | 2.984 | 4.409 | <=100 |
| Bootstrap joint geometry | 93.40% | 99.90% | 78.25% | >=80% |
| Stopping information share | 13.57% | 17.71% | 5.11% | >=5% |
| Stopping bootstrap LCB | 0% | 6.54% | 0% | >0% |
| Nonzero Stopping tasks | 2 | 3 | 1 | >=2 |
| Population admitted | no | yes | no | all required |

Population 1 failed the parent bootstrap lower-bound gates. Population 3 additionally failed
bootstrap joint geometry and the minimum nonzero-task gates. Population 2 is a positive local
result, but the protocol forbids one population from authorizing the whole experiment.

## Stopping Shape Behavior

The five executable Stopping submechanisms cover the six preregistered decision shapes through
explicit many-to-one structural mappings. Their observed Contract-success rates were:

| Submechanism | Population 1 | Population 2 | Population 3 |
| --- | ---: | ---: | ---: |
| Incomplete state must continue | 8/8 | 8/8 | 8/8 |
| Complete state: additional-call cost | 8/8 | 7/8 | 8/8 |
| Complete state: additional-call error risk | 8/8 | 8/8 | 8/8 |
| Uncertain source coverage | 7/8 | 6/8 | 8/8 |
| Unresolved conflict cannot stop | 6/8 | 6/8 | 1/8 |

The Runtime repair generalized: conflict state was observable and replayable in 24/24 population
instances. What did not generalize was its boundary location. The unresolved-conflict response was
0.75, 0.75, and 0.125 across populations. Population 3 therefore had only one informative
Stopping task, while the other four Stopping tasks were at the ceiling.

## Cross-population Stability

| Pair | Point maximum angle | Bootstrap alignment pass | Result |
| --- | ---: | ---: | --- |
| Population 1 vs 2 | 53.15 degrees | 38.10% | fail |
| Population 1 vs 3 | 27.81 degrees | 54.35% | fail |
| Population 2 vs 3 | 72.88 degrees | 23.30% | fail |

The point angle alone is insufficient: even Population 1 vs 3, whose point estimate is below the
45-degree threshold, has a wide 95% maximum-angle interval and fails bootstrap stability.

## Why Pooled Admission Would Be Wrong

Pooling all 60 tasks produces an apparently excellent diagnostic:

```text
boundary_task_fraction = 0.65
identifiable_rank = 6
top4_effective_rank = 3.4963
top4_condition_number = 3.7364
bootstrap_joint_geometry_pass_rate = 0.9995
stopping_parent_information_share = 0.1261
stopping_parent_bootstrap_lcb = 0.05595
```

Those values would pass the prior pooled contract, despite two failed populations and three failed
cross-population alignments. v25.35 therefore empirically validates the audit requirement that a
pooled result cannot rescue population-specific support failure.

## Finalizer Lineage

The 480 API rollouts completed under the immutable v1 contract. Initial local finalization then
failed because the new native contract omitted the behavior observer's
`task_expected_host_events` projection. No model call was repeated. The finalizer was repaired to
derive this public map from the three frozen population scenarios, and continuation was allowed
only after verifying:

- all 480 content-addressed checkpoint records were present;
- every record retained the original contract identity;
- every non-finalizer implementation hash still matched the frozen contract;
- only the finalizer source hash changed.

The report and manifest preserve both execution and finalizer implementation hashes and set
`posthoc_finalizer_fix_applied=true`.

## Scientific Interpretation

v25.35 is a negative stable-support result, not a Runtime failure and not evidence that Stopping is
absent. It establishes:

1. the v25.34 observability repair generalizes across fresh tasks and action orderings;
2. one fresh population supports the full per-population geometry;
3. Stopping information remains task-instance sensitive and is not stable across populations;
4. the claimed Top-4 subspace is not yet population-stable;
5. pooled geometry materially overstates support reliability.

The next experiment must redesign support before collecting Confirmation. It should increase
independent task-instance support per Stopping shape and preregister difficulty controls that place
multiple Stopping tasks near the boundary without selecting them post hoc. Threshold relaxation,
pooled rescue, historical reclassification, and immediate Pro expansion are not permitted.

## Authoritative Artifacts

- `finance_v25_35_cross_population_stable_protocol_v1_20260816/`
- `finance_v25_35_cross_population_stable_development_population_{1,2,3}_v1_20260816/`
- `finance_v25_35_cross_population_stable_contract_v1_20260816/`
- `finance_v25_35_cross_population_stable_development_v1_20260816/`

