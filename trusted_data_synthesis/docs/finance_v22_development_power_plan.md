# Finance v22 Development Population And Power Study

Status date: 2026-08-08

Current status: `materializer_action_contract_requalification`. The initial Explorer distribution
is qualified and two state-materializer diagnostics have completed. Development target gradients
have not started. This document records the pre-outcome design, immutable inputs, observed
materialization limits, and scientific boundaries for the successor to the cancelled v21 run.

## Scientific Question

v20 showed that strict FP32 execution was reliable while its finite target was not identifiable.
v21 began a larger direct-coordinate run, but it was stopped by operator request before completion
so that the target-observability protocol could be revised. v22 first asks a more basic question:

> What task, Objective-support, and trajectory-realization variance must a target experiment absorb,
> and how many independent tasks are required to detect an effect large enough to change a VTDO
> state probability by two percentage points?

This is a Development-only variance and power study. It cannot inspect Validation or Authorization,
evaluate GP-C, authorize Contribution, or update a VTDO distribution.

## Frozen Development Population

The target population was selected before any v22 Explorer or target outcome was observed. It is
sampled from the existing 420-task real Finance pool while excluding all six v21 target tasks,
their semantic signatures, and their 58 Evidence versions.

| Component | Frozen support |
| --- | ---: |
| Independent target tasks | 30 |
| Finance task families | 6 |
| Tasks per family | 5 |
| Accepted quotient states | 100 |
| States per task | 3-5 |
| Public Evidence versions | 312 |
| Shared Evidence across target tasks | 0 |
| Unconditioned Explorer replicas per task | 10 planned |
| State-conditioned realizations per state | 5 planned |

The six task families are comparison, derived growth comparison, registered ratio, temporal
absolute change, temporal average, and temporal growth.

## Frozen Development Objective Support

The Objective role contains 64 real training records selected from tasks disjoint from both the
v22 target population and the six historical v21 targets. The selector rejects shared task IDs,
semantic signatures, and Evidence versions. The 64 records are frozen into eight deterministic,
mutually exclusive micro-splits of eight records each. Each split covers five or six task families.

No Validation or Authorization partition exists in this artifact. The explicit access fields are
`forbidden`, GP-C execution is false, and production Contribution remains zero.

## Minimum Practical Effect

The engineering MPE is derived from the frozen anchored VTDO update rather than assigned in raw
Objective units. For each task-state coordinate, the implementation finds the minimum centered
state-to-rest Contribution contrast whose isolated change moves the selected next-round state
probability by at least:

```text
delta_pi = 0.02
```

The calculation holds the current distribution, uniform coverage anchor, novelty transform, and
task-conditional Reachability estimates fixed. It reports a state contrast, not only the selected
state's centered amplitude. This remains an engineering threshold, not a business effect or a
claim about downstream model accuracy.

## Planned Development Measurements

The data stage will collect:

- 300 unconditioned DeepSeek Explorer observations;
- exactly five independent state-conditioned realizations for each of 100 states;
- natural state frequencies and entropy by task;
- task-conditional on-target rates and Wilson intervals;
- off-target transition matrices;
- API success, contract repair, token, cost, and retry telemetry;
- the update-derived MPE distribution.

Only after these pre-target quantities are frozen may the Development target study estimate nested
variance across task, task family, Objective micro-split, realization, and numeric replay. The final
Validation task count is not frozen until Monte Carlo power simulation uses those observed variance
components.

## Materializer Diagnostics

The unconditioned DeepSeek Explorer stage completed before state-conditioned materialization:

| Measure | Observed |
| --- | ---: |
| Requested trajectories | 300 |
| Valid trajectories | 300 |
| Catalog hits | 298 |
| Valid off-catalog trajectories | 2 |
| API / JSON-contract success | 900 / 900 |

The first DeepSeek state-conditioned run released 315 of 500 requested realizations before the
provider exhausted its prepaid credit. It remains a partial model-sensitivity artifact and is not
silently combined with later local-model runs.

The first local Qwen diagnostic used Action Prompt v11 and Search Prompt v7 with one attempt per
state. The seven-replica serving pool completed every HTTP request, but only 8 of 100 requested
state realizations were independently verified and released:

| Measure | Observed |
| --- | ---: |
| API calls / HTTP successes | 258 / 258 |
| JSON-contract successes | 183 |
| Generation successes / failures | 25 / 75 |
| Independently released trajectories | 8 |
| Invalid trajectories | 16 |
| Off-target trajectories | 1 |

The failure taxonomy localized the remaining issue to Action Plan realization rather than serving
or search. Common failures were truncated or malformed JSON, direct semantic operations emitted for
transparent-projection states, and lookup projections emitted for baseline states. Action Prompt
v12 therefore makes the following generic, public-only changes:

- action catalogs contain only fields required to choose and wire operations;
- baseline and projection modes receive mutually exclusive typed examples;
- public evidence roles, terminal-operation constraints, and topology rules are repeated in a
  final recency block;
- contract repair explicitly changes topology for `state_execution_*` failures;
- the local structured-generation profile uses temperature 0.2 and 2,048 output tokens.

These changes do not let the Host select evidence or construct the operation graph. A fresh
100-state smoke run must pass a predeclared engineering threshold before the five-realization run is
allowed. The failed diagnostic remains immutable and auditable.

The predeclared smoke threshold is: at least 70 of 100 requested states released, 100% HTTP success,
no identity or public/oracle-isolation violation, at most two search-contract failures, at most ten
combined baseline/projection topology failures, at least one release from every registered task
family, and at least one release from every registered state strategy. Failing any item blocks the
500-realization run and permits only another versioned engineering diagnostic.

## Fail-Closed Transition

The next permitted transition is a Development target measurement. A future Validation population
must contain 48-60 fresh tasks and remain disjoint in task ID, Evidence version, and semantic
signature. Direct coordinates precede any block design. GP-C remains inaccessible until an
independent target is either statistically identifiable or demonstrably within the frozen
practical-equivalence region.

## Immutable References

- `artifacts/vtdo_experiment/finance_v22_development_population30_v1_20260807/`
- `artifacts/vtdo_experiment/finance_v22_development_objective64_v1_20260807/`
- `artifacts/vtdo_experiment/finance_v21_target_observability_population420_v1_20260807/`
- `artifacts/vtdo_experiment/finance_v21_target_observability_population6_v1_20260807/`
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_development_power.py`
