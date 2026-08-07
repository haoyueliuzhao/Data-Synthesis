# Finance v22 Development Population And Power Study

Status date: 2026-08-07

Current status: `development_support_frozen`. Real API observations and GPU target measurements have
not yet started. This document records the pre-outcome design, immutable inputs, and scientific
boundaries for the successor to the cancelled v21 run.

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
